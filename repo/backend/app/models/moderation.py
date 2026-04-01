from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class ModerationReasonCode(BaseModel):
    __tablename__ = "moderation_reason_codes"

    code: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="content")


class ModerationQueueItem(BaseModel):
    __tablename__ = "moderation_queue"

    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id"), nullable=True, index=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open", index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", index=True)
    latest_reason_code: Mapped[str | None] = mapped_column(ForeignKey("moderation_reason_codes.code"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actions: Mapped[list["ModerationAction"]] = relationship(
        "ModerationAction",
        back_populates="queue_item",
        cascade="all, delete-orphan",
    )


class ModerationAction(BaseModel):
    __tablename__ = "moderation_actions"

    moderation_item_id: Mapped[str] = mapped_column(ForeignKey("moderation_queue.id"), nullable=False, index=True)
    operator_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(ForeignKey("moderation_reason_codes.code"), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    operator_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    queue_item: Mapped[ModerationQueueItem] = relationship("ModerationQueueItem", back_populates="actions")


class RoleChangeEvent(BaseModel):
    __tablename__ = "role_change_events"

    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    target_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role_name: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="applied", index=True)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


__all__ = [
    "ModerationAction",
    "ModerationQueueItem",
    "ModerationReasonCode",
    "RoleChangeEvent",
]
