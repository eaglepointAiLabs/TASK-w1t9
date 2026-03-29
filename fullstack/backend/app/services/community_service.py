from __future__ import annotations

import json
from datetime import timedelta

import structlog

from app.extensions import db
from app.repositories.community_repository import CommunityRepository
from app.repositories.moderation_repository import ModerationRepository
from app.services.errors import AppError
from app.services.moderation_service import ModerationService
from app.services.time_utils import serialize_utc_datetime, utc_now_naive


logger = structlog.get_logger(__name__)


class CommunityService:
    def __init__(self, repository: CommunityRepository) -> None:
        self.repository = repository

    def toggle_like(self, user_id: str, payload: dict):
        target_type = (payload.get("target_type") or "").strip()
        target_id = (payload.get("target_id") or "").strip()
        self._validate_target(target_type, target_id)
        self._enforce_throttle(user_id, "like_toggle", target_type, target_id)
        like = self.repository.get_like(user_id, target_type, target_id)
        active = False
        if like is None:
            self.repository.create_like(user_id=user_id, target_type=target_type, target_id=target_id)
            active = True
        else:
            self.repository.delete_like(like)
        db.session.commit()
        return {"active": active, "count": self.repository.count_likes(target_type, target_id)}

    def toggle_favorite(self, user_id: str, payload: dict):
        target_type = (payload.get("target_type") or "").strip()
        target_id = (payload.get("target_id") or "").strip()
        self._validate_target(target_type, target_id)
        self._enforce_throttle(user_id, "favorite_toggle", target_type, target_id)
        favorite = self.repository.get_favorite(user_id, target_type, target_id)
        active = False
        if favorite is None:
            self.repository.create_favorite(user_id=user_id, target_type=target_type, target_id=target_id)
            active = True
        else:
            self.repository.delete_favorite(favorite)
        db.session.commit()
        return {"active": active, "count": self.repository.count_favorites(target_type, target_id)}

    def create_comment(self, user, payload: dict):
        target_type = (payload.get("target_type") or "").strip()
        target_id = (payload.get("target_id") or "").strip()
        body = (payload.get("body") or "").strip()
        self._validate_target(target_type, target_id)
        if len(body) < 3:
            raise AppError("validation_error", "Comment must be at least 3 characters.", 400)
        self._enforce_throttle(user.id, "comment", target_type, target_id)
        self._enforce_cooldown(user.id, "comment", target_type, target_id, seconds=30)
        self._enforce_block_rules(user.id, target_type, target_id)
        comment = self.repository.create_comment(author_user_id=user.id, target_type=target_type, target_id=target_id, body=body)
        db.session.commit()
        logger.info("community.comment_created", comment_id=comment.id, user_id=user.id)
        return comment

    def create_report(self, user, payload: dict):
        target_type = (payload.get("target_type") or "").strip()
        target_id = (payload.get("target_id") or "").strip()
        reason_code = (payload.get("reason_code") or "").strip()
        details = (payload.get("details") or "").strip()
        self._validate_target(target_type, target_id)
        if reason_code not in {"abuse", "spam", "harassment", "other"}:
            raise AppError("validation_error", "Invalid report reason code.", 400)
        self._enforce_throttle(user.id, "report", target_type, target_id)
        report = self.repository.create_report(
            reporter_user_id=user.id,
            target_type=target_type,
            target_id=target_id,
            reason_code=reason_code,
            details=details,
            status="open",
        )
        db.session.commit()
        ModerationService(ModerationRepository()).ensure_queue_item_for_report(report)
        return report

    def block_user(self, user_id: str, blocked_user_id: str):
        if user_id == blocked_user_id:
            raise AppError("validation_error", "You cannot block yourself.", 400)
        existing = self.repository.get_block(user_id, blocked_user_id)
        if existing is None:
            self.repository.create_block(user_id=user_id, blocked_user_id=blocked_user_id)
            db.session.commit()
        return {"blocked_user_id": blocked_user_id}

    def unblock_user(self, user_id: str, blocked_user_id: str):
        existing = self.repository.get_block(user_id, blocked_user_id)
        if existing is None:
            raise AppError("not_found", "Block record not found.", 404)
        self.repository.delete_block(existing)
        db.session.commit()
        return {"blocked_user_id": blocked_user_id}

    def list_posts(self):
        return self.repository.list_posts()

    def list_comments(self, target_type: str, target_id: str):
        return self.repository.list_comments(target_type, target_id)

    def _validate_target(self, target_type: str, target_id: str) -> None:
        if target_type not in {"dish", "post"} or not target_id:
            raise AppError("validation_error", "Invalid target.", 400)

    def _enforce_throttle(self, user_id: str, action_type: str, target_type: str, target_id: str) -> None:
        now = utc_now_naive()
        recent = self.repository.recent_action_count(user_id, action_type, now - timedelta(minutes=1))
        if recent >= 5:
            raise AppError(
                "throttled",
                "Too many rapid community actions. Try again shortly.",
                429,
                {"retry_after_seconds": 60},
            )
        self.repository.create_cooldown_event(
            user_id=user_id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            expires_at=now + timedelta(seconds=60),
            details_json=json.dumps({"kind": "throttle_window"}),
        )

    def _enforce_cooldown(self, user_id: str, action_type: str, target_type: str, target_id: str, seconds: int) -> None:
        now = utc_now_naive()
        cooldown = self.repository.active_cooldown(user_id, f"{action_type}_cooldown", target_type, target_id, now)
        if cooldown is not None:
            raise AppError(
                "cooldown_active",
                "You need to wait before posting again.",
                429,
                {"expires_at": serialize_utc_datetime(cooldown.expires_at)},
            )
        self.repository.create_cooldown_event(
            user_id=user_id,
            action_type=f"{action_type}_cooldown",
            target_type=target_type,
            target_id=target_id,
            expires_at=now + timedelta(seconds=seconds),
            details_json=json.dumps({"seconds": seconds}),
        )

    def _enforce_block_rules(self, user_id: str, target_type: str, target_id: str) -> None:
        if target_type != "post":
            return
        post = self.repository.get_post(target_id)
        if post and self.repository.block_exists_between(user_id, post.author_user_id):
            raise AppError("blocked_interaction", "You cannot interact with this user.", 403)
