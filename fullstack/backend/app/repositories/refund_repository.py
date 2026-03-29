from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import ManagerStepupChallenge, PaymentTransaction, Refund, RefundEvent, RefundRiskEvent


class RefundRepository:
    def get_payment_by_reference(self, reference: str) -> PaymentTransaction | None:
        stmt = select(PaymentTransaction).where(PaymentTransaction.transaction_reference == reference)
        return db.session.scalar(stmt)

    def get_payment(self, payment_id: str) -> PaymentTransaction | None:
        stmt = select(PaymentTransaction).where(PaymentTransaction.id == payment_id)
        return db.session.scalar(stmt)

    def list_refunds_for_payment(self, payment_id: str) -> list[Refund]:
        stmt = select(Refund).where(Refund.payment_transaction_id == payment_id)
        return list(db.session.scalars(stmt))

    def create_refund(self, **kwargs) -> Refund:
        refund = Refund(**kwargs)
        db.session.add(refund)
        db.session.flush()
        return refund

    def create_refund_event(self, **kwargs) -> RefundEvent:
        event = RefundEvent(**kwargs)
        db.session.add(event)
        db.session.flush()
        return event

    def create_risk_event(self, **kwargs) -> RefundRiskEvent:
        event = RefundRiskEvent(**kwargs)
        db.session.add(event)
        db.session.flush()
        return event

    def list_recent_device_refunds(self, device_id: str, since: datetime) -> list[Refund]:
        stmt = select(Refund).where(Refund.device_id == device_id, Refund.created_at >= since)
        return list(db.session.scalars(stmt))

    def create_stepup_challenge(self, **kwargs) -> ManagerStepupChallenge:
        challenge = ManagerStepupChallenge(**kwargs)
        db.session.add(challenge)
        db.session.flush()
        return challenge

    def get_active_stepup(self, refund_id: str) -> ManagerStepupChallenge | None:
        stmt = select(ManagerStepupChallenge).where(
            ManagerStepupChallenge.refund_id == refund_id,
            ManagerStepupChallenge.status == "pending",
        )
        return db.session.scalar(stmt)

    def get_refund(self, refund_id: str) -> Refund | None:
        stmt = select(Refund).options(joinedload(Refund.events)).where(Refund.id == refund_id)
        return db.session.execute(stmt).unique().scalar_one_or_none()

    def list_risk_events(self) -> list[RefundRiskEvent]:
        stmt = select(RefundRiskEvent).order_by(RefundRiskEvent.created_at.desc())
        return list(db.session.scalars(stmt))
