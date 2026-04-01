from __future__ import annotations

import json

import structlog

from app.extensions import db
from app.repositories.auth_repository import AuthRepository
from app.repositories.moderation_repository import ModerationRepository
from app.services.auth_service import AuthService
from app.services.errors import AppError
from app.services.rbac_service import RBACService


logger = structlog.get_logger(__name__)

VALID_OUTCOMES = {"dismiss", "warn", "hide", "remove", "suspend"}


class ModerationService:
    def __init__(self, repository: ModerationRepository) -> None:
        self.repository = repository
        self.rbac = RBACService()
        self.auth_service = AuthService(AuthRepository())

    def ensure_queue_item_for_report(self, report) -> None:
        existing = self.repository.find_queue_item_by_report(report.id)
        if existing is not None:
            return
        priority = "high" if report.reason_code in {"abuse", "harassment"} else "normal"
        self.repository.create_queue_item(
            report_id=report.id,
            target_type=report.target_type,
            target_id=report.target_id,
            target_user_id=None,
            status="open",
            priority=priority,
            latest_reason_code=report.reason_code,
            notes=report.details or "",
        )
        db.session.commit()

    def list_queue(self, current_roles: list[str], status: str | None = None):
        self.rbac.require_roles(current_roles, ["Moderator"])
        return self.repository.list_queue(status=status)

    def decide_item(self, item_id: str, payload: dict, operator, current_roles: list[str]):
        self.rbac.require_roles(current_roles, ["Moderator"])
        item = self.repository.get_queue_item(item_id)
        if item is None:
            raise AppError("not_found", "Moderation item not found.", 404)

        outcome = (payload.get("outcome") or "").strip()
        reason_code = (payload.get("reason_code") or "").strip()
        operator_notes = (payload.get("operator_notes") or "").strip()
        if outcome not in VALID_OUTCOMES:
            raise AppError("validation_error", "Invalid moderation outcome.", 400)
        if not reason_code:
            raise AppError("validation_error", "Reason code is required.", 400)
        if not operator_notes:
            raise AppError("validation_error", "Operator notes are required.", 400)

        reason = next((code for code in self.repository.list_reason_codes() if code.code == reason_code), None)
        if reason is None:
            raise AppError("validation_error", "Unknown moderation reason code.", 400)

        from_status = item.status
        to_status = "dismissed" if outcome == "dismiss" else "actioned"
        item.status = to_status
        item.latest_reason_code = reason_code
        item.notes = operator_notes
        db.session.add(item)
        action = self.repository.create_action(
            moderation_item_id=item.id,
            operator_user_id=operator.id,
            reason_code=reason_code,
            outcome=outcome,
            operator_notes=operator_notes,
            from_status=from_status,
            to_status=to_status,
        )
        db.session.commit()
        logger.info("moderation.decision", item_id=item.id, outcome=outcome, operator_id=operator.id)
        return item

    def get_history(self, item_id: str, current_roles: list[str]):
        self.rbac.require_roles(current_roles, ["Moderator"])
        item = self.repository.get_queue_item(item_id)
        if item is None:
            raise AppError("not_found", "Moderation item not found.", 404)
        return item

    def change_role(
        self,
        payload: dict,
        operator,
        current_roles: list[str],
        current_session_id: str | None,
        nonce_value: str | None,
    ):
        self.rbac.require_roles(current_roles, ["Finance Admin"])

        target_username = (payload.get("target_username") or "").strip().lower()
        role_name = (payload.get("role_name") or "").strip()
        action = (payload.get("action") or "").strip().lower()
        if action not in {"grant", "revoke"}:
            raise AppError("validation_error", "action must be grant or revoke.", 400)

        target = self.repository.get_user_by_username(target_username)
        if target is None:
            raise AppError("not_found", "Target user not found.", 404)
        if target.id == operator.id:
            raise AppError("forbidden", "You cannot change your own role assignments.", 403)
        role = self.repository.get_role(role_name)
        if role is None:
            raise AppError("validation_error", "Role not found.", 400)
        self.auth_service.consume_nonce(current_session_id, "admin:role_change", nonce_value)

        existing = self.repository.get_user_role(target.id, role.id)
        status = "applied"
        changed = False
        if action == "grant" and existing is None:
            self.repository.create_user_role(target.id, role.id)
            changed = True
        elif action == "revoke" and existing is not None:
            if role.name == "Finance Admin" and self.repository.count_users_with_role("Finance Admin") <= 1:
                raise AppError(
                    "validation_error",
                    "At least one Finance Admin must remain assigned.",
                    409,
                )
            self.repository.delete_user_role(existing)
            changed = True
        else:
            status = "noop"

        event = self.repository.create_role_change_event(
            actor_user_id=operator.id,
            target_user_id=target.id,
            role_name=role.name,
            action=action,
            status=status,
            details_json=json.dumps({"target_username": target.username, "changed": changed}),
        )
        db.session.commit()
        logger.info(
            "governance.role_changed",
            actor_id=operator.id,
            target_id=target.id,
            role_name=role.name,
            action=action,
            status=status,
        )
        return event
