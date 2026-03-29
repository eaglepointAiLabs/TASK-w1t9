from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import structlog
from flask import current_app

from app.extensions import db
from app.repositories.auth_repository import AuthRepository
from app.repositories.refund_repository import RefundRepository
from app.services.auth_service import AuthService
from app.services.catalog_validation import parse_price
from app.services.errors import AppError
from app.services.rbac_service import RBACService
from app.services.time_utils import utc_now_naive


logger = structlog.get_logger(__name__)


class RefundService:
    def __init__(self, repository: RefundRepository) -> None:
        self.repository = repository
        self.rbac = RBACService()
        self.auth_service = AuthService(AuthRepository())

    def create_refund(
        self,
        payload: dict,
        current_user,
        current_roles: list[str],
        current_session_id: str | None,
        nonce_value: str | None,
        device_id: str,
    ):
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        self.auth_service.consume_nonce(current_session_id, "refund:create", nonce_value)

        payment = self.repository.get_payment_by_reference((payload.get("transaction_reference") or "").strip())
        if payment is None:
            raise AppError("not_found", "Payment transaction not found.", 404)
        if payment.status != "success":
            raise AppError("validation_error", "Only successful captures can be refunded.", 400)

        requested_amount = parse_price(payload.get("refund_amount"), "refund_amount")
        requested_route = (payload.get("route") or "").strip()
        if requested_route != payment.channel:
            raise AppError("original_route_required", "Refund must use the original capture route.", 400)

        existing_refunds = self.repository.list_refunds_for_payment(payment.id)
        refunded_total = sum(
            refund.requested_amount
            for refund in existing_refunds
            if refund.status in {"approved", "pending_stepup", "held"}
        )
        if refunded_total + requested_amount > payment.capture_amount:
            raise AppError(
                "refund_cap_exceeded",
                "Refund total exceeds captured amount.",
                400,
                {"captured_amount": f"{payment.capture_amount:.2f}", "already_refunded": f"{refunded_total:.2f}"},
            )

        risk_flags = []
        recent_device_refunds = self.repository.list_recent_device_refunds(device_id, utc_now_naive() - timedelta(minutes=30))
        if len(recent_device_refunds) >= 3:
            risk_flags.append({"risk_code": "device_refund_burst", "severity": "high", "action_taken": "hold"})

        if requested_amount > Decimal("50.00"):
            risk_flags.append({"risk_code": "amount_stepup_threshold", "severity": "medium", "action_taken": "stepup"})

        refund_status = "approved"
        hold_reason = ""
        stepup_required = "false"
        if risk_flags:
            refund_status = "pending_stepup"
            hold_reason = "; ".join(flag["risk_code"] for flag in risk_flags)
            stepup_required = "true"

        refund = self.repository.create_refund(
            payment_transaction_id=payment.id,
            order_id=payment.order_id,
            transaction_reference=payment.transaction_reference,
            refund_reference=f"refund-{uuid4().hex[:12]}",
            original_route=requested_route,
            requested_amount=requested_amount,
            status=refund_status,
            requested_by_user_id=current_user.id,
            device_id=device_id,
            hold_reason=hold_reason,
            stepup_required=stepup_required,
            approved_at=utc_now_naive() if refund_status == "approved" else None,
        )
        self.repository.create_refund_event(
            refund_id=refund.id,
            event_type="created",
            from_status=None,
            to_status=refund_status,
            actor_user_id=current_user.id,
            details_json=json.dumps({"route": requested_route, "amount": f"{requested_amount:.2f}"}),
        )

        for flag in risk_flags:
            self.repository.create_risk_event(
                refund_id=refund.id,
                payment_transaction_id=payment.id,
                device_id=device_id,
                risk_code=flag["risk_code"],
                severity=flag["severity"],
                action_taken=flag["action_taken"],
                details_json=json.dumps({"refund_amount": f"{requested_amount:.2f}"}),
            )

        if refund_status == "pending_stepup":
            self.repository.create_stepup_challenge(
                refund_id=refund.id,
                operator_user_id=current_user.id,
                status="pending",
                reason=hold_reason or "step-up confirmation required",
                expires_at=utc_now_naive() + timedelta(minutes=5),
                completed_at=None,
            )

        db.session.commit()
        logger.info("refund.created", refund_id=refund.id, payment_id=payment.id, status=refund_status)
        return refund

    def confirm_stepup(
        self,
        refund_id: str,
        password: str,
        current_user,
        current_roles: list[str],
        current_session_id: str | None,
        nonce_value: str | None,
    ):
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        self.auth_service.consume_nonce(current_session_id, "refund:confirm", nonce_value)
        refund = self.repository.get_refund(refund_id)
        if refund is None:
            raise AppError("not_found", "Refund not found.", 404)
        challenge = self.repository.get_active_stepup(refund.id)
        if challenge is None or challenge.expires_at < utc_now_naive():
            raise AppError("stepup_missing", "Active step-up challenge not found.", 400)

        user = AuthRepository().get_user_by_username(current_user.username)
        if not password:
            raise AppError("stepup_failed", "Password confirmation is required.", 403)
        from app.extensions import bcrypt

        if not bcrypt.check_password_hash(user.password_hash, password):
            raise AppError("stepup_failed", "Password confirmation failed.", 403)

        from_status = refund.status
        refund.status = "approved"
        refund.approved_at = utc_now_naive()
        challenge.status = "completed"
        challenge.completed_at = utc_now_naive()
        db.session.add(refund)
        db.session.add(challenge)
        self.repository.create_refund_event(
            refund_id=refund.id,
            event_type="stepup_confirmed",
            from_status=from_status,
            to_status="approved",
            actor_user_id=current_user.id,
            details_json=json.dumps({"challenge_id": challenge.id}),
        )
        db.session.commit()
        logger.info("refund.stepup_confirmed", refund_id=refund.id)
        return refund

    def get_refund(self, refund_id: str, current_roles: list[str]):
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        refund = self.repository.get_refund(refund_id)
        if refund is None:
            raise AppError("not_found", "Refund not found.", 404)
        return refund

    def list_risk_events(self, current_roles: list[str]):
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        return self.repository.list_risk_events()
