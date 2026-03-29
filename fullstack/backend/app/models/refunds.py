from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class Refund(BaseModel):
    __tablename__ = "refunds"

    payment_transaction_id: Mapped[str] = mapped_column(ForeignKey("payment_transactions.id"), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    transaction_reference: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    refund_reference: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    original_route: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    hold_reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    stepup_required: Mapped[str] = mapped_column(String(5), nullable=False, default="false")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    events: Mapped[list["RefundEvent"]] = relationship(
        "RefundEvent",
        back_populates="refund",
        cascade="all, delete-orphan",
    )


class RefundEvent(BaseModel):
    __tablename__ = "refund_events"

    refund_id: Mapped[str] = mapped_column(ForeignKey("refunds.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    refund: Mapped[Refund] = relationship("Refund", back_populates="events")


class RefundRiskEvent(BaseModel):
    __tablename__ = "refund_risk_events"

    refund_id: Mapped[str | None] = mapped_column(ForeignKey("refunds.id"), nullable=True, index=True)
    payment_transaction_id: Mapped[str] = mapped_column(ForeignKey("payment_transactions.id"), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    risk_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    action_taken: Mapped[str] = mapped_column(String(40), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class ManagerStepupChallenge(BaseModel):
    __tablename__ = "manager_stepup_challenges"

    refund_id: Mapped[str] = mapped_column(ForeignKey("refunds.id"), nullable=False, index=True)
    operator_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


__all__ = [
    "ManagerStepupChallenge",
    "Refund",
    "RefundEvent",
    "RefundRiskEvent",
]
