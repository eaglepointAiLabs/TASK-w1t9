from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    ModerationAction,
    ModerationQueueItem,
    ModerationReasonCode,
    Report,
    Role,
    RoleChangeEvent,
    User,
    UserRole,
)


class ModerationRepository:
    def get_report(self, report_id: str) -> Report | None:
        stmt = select(Report).where(Report.id == report_id)
        return db.session.scalar(stmt)

    def get_or_create_reason_code(self, code: str, label: str, description: str, category: str) -> ModerationReasonCode:
        stmt = select(ModerationReasonCode).where(ModerationReasonCode.code == code)
        existing = db.session.scalar(stmt)
        if existing is not None:
            return existing
        reason = ModerationReasonCode(code=code, label=label, description=description, category=category)
        db.session.add(reason)
        db.session.flush()
        return reason

    def list_reason_codes(self) -> list[ModerationReasonCode]:
        stmt = select(ModerationReasonCode).order_by(ModerationReasonCode.category.asc(), ModerationReasonCode.label.asc())
        return list(db.session.scalars(stmt))

    def create_queue_item(self, **kwargs) -> ModerationQueueItem:
        item = ModerationQueueItem(**kwargs)
        db.session.add(item)
        db.session.flush()
        return item

    def find_queue_item_by_report(self, report_id: str) -> ModerationQueueItem | None:
        stmt = select(ModerationQueueItem).where(ModerationQueueItem.report_id == report_id)
        return db.session.scalar(stmt)

    def list_queue(self, status: str | None = None) -> list[ModerationQueueItem]:
        stmt = select(ModerationQueueItem).options(joinedload(ModerationQueueItem.actions)).order_by(ModerationQueueItem.created_at.desc())
        if status:
            stmt = stmt.where(ModerationQueueItem.status == status)
        return list(db.session.execute(stmt).unique().scalars())

    def get_queue_item(self, item_id: str) -> ModerationQueueItem | None:
        stmt = (
            select(ModerationQueueItem)
            .options(joinedload(ModerationQueueItem.actions))
            .where(ModerationQueueItem.id == item_id)
        )
        return db.session.execute(stmt).unique().scalar_one_or_none()

    def create_action(self, **kwargs) -> ModerationAction:
        action = ModerationAction(**kwargs)
        db.session.add(action)
        db.session.flush()
        return action

    def get_user_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return db.session.scalar(stmt)

    def get_role(self, role_name: str) -> Role | None:
        stmt = select(Role).where(Role.name == role_name)
        return db.session.scalar(stmt)

    def count_users_with_role(self, role_name: str) -> int:
        stmt = (
            select(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name == role_name)
        )
        return len(list(db.session.scalars(stmt)))

    def get_user_role(self, user_id: str, role_id: str) -> UserRole | None:
        stmt = select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        return db.session.scalar(stmt)

    def create_user_role(self, user_id: str, role_id: str) -> UserRole:
        assignment = UserRole(user_id=user_id, role_id=role_id)
        db.session.add(assignment)
        db.session.flush()
        return assignment

    def delete_user_role(self, assignment: UserRole) -> None:
        db.session.delete(assignment)
        db.session.flush()

    def create_role_change_event(self, **kwargs) -> RoleChangeEvent:
        event = RoleChangeEvent(**kwargs)
        db.session.add(event)
        db.session.flush()
        return event
