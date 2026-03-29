from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class PaymentTransaction(BaseModel):
    __tablename__ = "payment_transactions"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    transaction_reference: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    channel: Mapped[str] = mapped_column(String(80), nullable=False, default="offline_wechat_simulator")
    capture_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False, default="local_capture")
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failure_reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    callbacks: Mapped[list["PaymentCallback"]] = relationship(
        "PaymentCallback",
        back_populates="payment_transaction",
        cascade="all, delete-orphan",
    )


class PaymentCallback(BaseModel):
    __tablename__ = "payment_callbacks"

    payment_transaction_id: Mapped[str | None] = mapped_column(ForeignKey("payment_transactions.id"), nullable=True, index=True)
    transaction_reference: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(120), nullable=False, default="local_simulator")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    signature: Mapped[str] = mapped_column(String(255), nullable=False)
    key_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    verification_message: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duplicate_of_callback_id: Mapped[str | None] = mapped_column(ForeignKey("payment_callbacks.id"), nullable=True, index=True)
    payment_transaction: Mapped[PaymentTransaction | None] = relationship("PaymentTransaction", back_populates="callbacks")


class CallbackDedupKey(BaseModel):
    __tablename__ = "callback_dedup_keys"

    transaction_reference: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    callback_id: Mapped[str] = mapped_column(ForeignKey("payment_callbacks.id"), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)


class GatewaySigningKey(BaseModel):
    __tablename__ = "gateway_signing_keys"

    key_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(40), nullable=False, default="HMAC-SHA256")
    active_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


__all__ = [
    "CallbackDedupKey",
    "GatewaySigningKey",
    "PaymentCallback",
    "PaymentTransaction",
]
