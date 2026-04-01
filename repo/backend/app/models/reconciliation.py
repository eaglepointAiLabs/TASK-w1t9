from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class ReconciliationRun(BaseModel):
    __tablename__ = "reconciliation_runs"

    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    imported_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    imported_filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="completed", index=True)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exception_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rows: Mapped[list["ReconciliationRow"]] = relationship(
        "ReconciliationRow",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    exceptions: Mapped[list["ReconciliationException"]] = relationship(
        "ReconciliationException",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class ReconciliationRow(BaseModel):
    __tablename__ = "reconciliation_rows"

    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_reference: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    terminal_status: Mapped[str] = mapped_column(String(40), nullable=False)
    terminal_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    terminal_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    matched_payment_id: Mapped[str | None] = mapped_column(ForeignKey("payment_transactions.id"), nullable=True, index=True)
    match_status: Mapped[str] = mapped_column(String(40), nullable=False, default="matched", index=True)
    raw_row_json: Mapped[str] = mapped_column(Text, nullable=False)
    run: Mapped[ReconciliationRun] = relationship("ReconciliationRun", back_populates="rows")


class ReconciliationException(BaseModel):
    __tablename__ = "reconciliation_exceptions"

    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id"), nullable=False, index=True)
    row_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_rows.id"), nullable=False, index=True)
    transaction_reference: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    exception_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    details_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open", index=True)
    resolved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    run: Mapped[ReconciliationRun] = relationship("ReconciliationRun", back_populates="exceptions")
    actions: Mapped[list["ReconciliationAction"]] = relationship(
        "ReconciliationAction",
        back_populates="exception",
        cascade="all, delete-orphan",
    )


class ReconciliationAction(BaseModel):
    __tablename__ = "reconciliation_actions"

    exception_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_exceptions.id"), nullable=False, index=True)
    operator_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    exception: Mapped[ReconciliationException] = relationship("ReconciliationException", back_populates="actions")


__all__ = [
    "ReconciliationAction",
    "ReconciliationException",
    "ReconciliationRow",
    "ReconciliationRun",
]
