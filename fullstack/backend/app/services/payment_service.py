from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

import structlog
from flask import current_app

from app.extensions import db
from app.repositories.payment_repository import PaymentRepository
from app.services.catalog_validation import parse_price
from app.services.errors import AppError
from app.services.payment_security import PaymentSecurity
from app.services.rbac_service import RBACService
from app.services.time_utils import ensure_utc_naive, utc_now_naive


logger = structlog.get_logger(__name__)


class PaymentService:
    def __init__(self, repository: PaymentRepository) -> None:
        self.repository = repository
        self.rbac = RBACService()
        self.security = PaymentSecurity(
            PaymentSecurity.derive_fernet_key(current_app.config["KEY_ENCRYPTION_SECRET"])
        )

    def create_signing_key(
        self,
        key_id: str,
        secret: str,
        active_from: datetime,
        expires_at: datetime | None,
        is_active: bool = True,
    ):
        existing = self.repository.get_signing_key(key_id)
        if existing is not None:
            return existing
        key = self.repository.create_signing_key(
            key_id=key_id,
            encrypted_secret=self.security.encrypt_secret(secret),
            active_from=active_from,
            expires_at=expires_at,
            is_active=is_active,
        )
        db.session.commit()
        return key

    def capture_payment(self, payload: dict, current_roles: list[str]):
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        order = self.repository.get_order(payload.get("order_id"))
        if order is None:
            raise AppError("not_found", "Order not found.", 404)
        amount = parse_price(payload.get("capture_amount") or order.total_amount, "capture_amount")
        transaction = self.repository.create_transaction(
            order_id=order.id,
            transaction_reference=(payload.get("transaction_reference") or "").strip(),
            channel=(payload.get("channel") or "offline_wechat_simulator").strip(),
            capture_amount=amount,
            currency=(payload.get("currency") or "USD").strip().upper(),
            status=(payload.get("status") or "pending").strip(),
            source=(payload.get("source") or "local_capture").strip(),
            captured_at=utc_now_naive() if payload.get("status") == "success" else None,
            failure_reason=(payload.get("failure_reason") or "").strip(),
        )
        db.session.commit()
        logger.info("payments.capture_created", order_id=order.id, payment_id=transaction.id, reference=transaction.transaction_reference)
        return transaction

    def verify_callback_preview(self, package: dict, current_roles: list[str]) -> dict:
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        return self._verify_package(package)

    def import_callback(self, package: dict, current_roles: list[str]) -> dict:
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        reference = (package.get("transaction_reference") or "").strip()
        if not reference:
            raise AppError("validation_error", "transaction_reference is required.", 400)

        active_key = self.repository.get_active_dedup_key(reference)
        if active_key is not None:
            logger.info("payments.callback_duplicate", reference=reference)
            return json.loads(active_key.response_json)

        verification = self._verify_package(package)
        callback = self.repository.create_callback(
            payment_transaction_id=None,
            transaction_reference=reference,
            source_name=(package.get("source_name") or "local_import").strip(),
            payload_json=self.security.canonical_payload(package.get("payload", {})),
            payload_hash=verification["payload_hash"],
            signature=(package.get("signature") or "").strip(),
            key_id=(package.get("key_id") or "").strip(),
            verification_status="verified" if verification["verified"] else "rejected",
            verification_message=verification["message"],
            processed_at=utc_now_naive(),
        )

        transaction = self.repository.get_transaction_by_reference(reference)
        if transaction is not None:
            callback.payment_transaction_id = transaction.id
            callback.payment_transaction = transaction
            transaction.status = package.get("payload", {}).get("status", transaction.status)
            if transaction.status == "success":
                transaction.captured_at = utc_now_naive()
            if transaction.status == "failed":
                transaction.failure_reason = verification["message"]
            db.session.add(transaction)

        response = {
            "code": "ok" if verification["verified"] else "callback_rejected",
            "message": "Callback imported." if verification["verified"] else "Callback rejected.",
            "data": {
                "callback_id": callback.id,
                "transaction_reference": reference,
                "verification_status": callback.verification_status,
                "verification_message": callback.verification_message,
                "payload_hash": callback.payload_hash,
                "payment_id": transaction.id if transaction else None,
            },
        }
        existing = self.repository.get_any_dedup_key(reference)
        self.repository.upsert_dedup_key(
            existing,
            transaction_reference=reference,
            callback_id=callback.id,
            payload_hash=callback.payload_hash,
            expires_at=utc_now_naive() + timedelta(hours=24),
            response_json=json.dumps(response),
        )
        db.session.commit()
        logger.info(
            "payments.callback_imported",
            reference=reference,
            callback_id=callback.id,
            verification_status=callback.verification_status,
        )
        return response

    def get_payment(self, payment_id: str, current_roles: list[str]):
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        payment = self.repository.get_transaction(payment_id)
        if payment is None:
            raise AppError("not_found", "Payment not found.", 404)
        return payment

    def list_workspace(self, current_roles: list[str]):
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        return self.repository.list_transactions(), self.repository.list_signing_keys()

    def _verify_package(self, package: dict) -> dict:
        key_id = (package.get("key_id") or "").strip()
        signature = (package.get("signature") or "").strip()
        payload = package.get("payload") or {}
        if not key_id or not signature or not isinstance(payload, dict):
            raise AppError("validation_error", "key_id, signature, and payload are required.", 400)

        key = self.repository.get_signing_key(key_id)
        payload_hash = self.security.payload_hash(payload)
        if key is None:
            return {"verified": False, "message": "Unknown signing key.", "payload_hash": payload_hash}

        event_time = self.security.parse_event_time(payload.get("occurred_at"))
        if event_time is None:
            return {"verified": False, "message": "payload.occurred_at is required.", "payload_hash": payload_hash}
        event_time = self._normalize_datetime(event_time)
        active_from = self._normalize_datetime(key.active_from)
        expires_at = self._normalize_datetime(key.expires_at) if key.expires_at else None

        if event_time < active_from or (expires_at is not None and event_time > expires_at):
            return {"verified": False, "message": "Signing key is not valid for the event time.", "payload_hash": payload_hash}

        secret = self.security.decrypt_secret(key.encrypted_secret)
        verified = self.security.verify_signature(payload, signature, secret)
        return {
            "verified": verified,
            "message": "Signature verified." if verified else "Signature verification failed.",
            "payload_hash": payload_hash,
        }

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        return ensure_utc_naive(value)
