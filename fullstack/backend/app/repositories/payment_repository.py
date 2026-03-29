from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import CallbackDedupKey, GatewaySigningKey, Order, PaymentCallback, PaymentTransaction
from app.services.time_utils import utc_now_naive


class PaymentRepository:
    def get_order(self, order_id: str) -> Order | None:
        stmt = select(Order).where(Order.id == order_id)
        return db.session.scalar(stmt)

    def create_transaction(self, **kwargs) -> PaymentTransaction:
        transaction = PaymentTransaction(**kwargs)
        db.session.add(transaction)
        db.session.flush()
        return transaction

    def get_transaction(self, payment_id: str) -> PaymentTransaction | None:
        stmt = (
            select(PaymentTransaction)
            .options(joinedload(PaymentTransaction.callbacks))
            .where(PaymentTransaction.id == payment_id)
        )
        return db.session.execute(stmt).unique().scalar_one_or_none()

    def get_transaction_by_reference(self, reference: str) -> PaymentTransaction | None:
        stmt = (
            select(PaymentTransaction)
            .options(joinedload(PaymentTransaction.callbacks))
            .where(PaymentTransaction.transaction_reference == reference)
        )
        return db.session.execute(stmt).unique().scalar_one_or_none()

    def create_callback(self, **kwargs) -> PaymentCallback:
        callback = PaymentCallback(**kwargs)
        db.session.add(callback)
        db.session.flush()
        return callback

    def get_callback(self, callback_id: str) -> PaymentCallback | None:
        stmt = select(PaymentCallback).where(PaymentCallback.id == callback_id)
        return db.session.scalar(stmt)

    def get_active_dedup_key(self, reference: str) -> CallbackDedupKey | None:
        stmt = select(CallbackDedupKey).where(
            CallbackDedupKey.transaction_reference == reference,
            CallbackDedupKey.expires_at >= utc_now_naive(),
        )
        return db.session.scalar(stmt)

    def get_any_dedup_key(self, reference: str) -> CallbackDedupKey | None:
        stmt = select(CallbackDedupKey).where(CallbackDedupKey.transaction_reference == reference)
        return db.session.scalar(stmt)

    def upsert_dedup_key(self, existing: CallbackDedupKey | None, **kwargs) -> CallbackDedupKey:
        if existing is None:
            existing = CallbackDedupKey(**kwargs)
            db.session.add(existing)
        else:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            db.session.add(existing)
        db.session.flush()
        return existing

    def create_signing_key(self, **kwargs) -> GatewaySigningKey:
        key = GatewaySigningKey(**kwargs)
        db.session.add(key)
        db.session.flush()
        return key

    def get_signing_key(self, key_id: str) -> GatewaySigningKey | None:
        stmt = select(GatewaySigningKey).where(GatewaySigningKey.key_id == key_id)
        return db.session.scalar(stmt)

    def list_signing_keys(self) -> list[GatewaySigningKey]:
        stmt = select(GatewaySigningKey).order_by(GatewaySigningKey.active_from.desc())
        return list(db.session.scalars(stmt))

    def list_transactions(self) -> list[PaymentTransaction]:
        stmt = select(PaymentTransaction).order_by(PaymentTransaction.created_at.desc())
        return list(db.session.scalars(stmt))
