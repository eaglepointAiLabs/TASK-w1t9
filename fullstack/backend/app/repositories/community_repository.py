from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.extensions import db
from app.models import Comment, CooldownEvent, Favorite, Like, Post, Report, UserBlock


class CommunityRepository:
    def get_post(self, post_id: str) -> Post | None:
        stmt = select(Post).where(Post.id == post_id)
        return db.session.scalar(stmt)

    def get_comment(self, comment_id: str) -> Comment | None:
        stmt = select(Comment).where(Comment.id == comment_id)
        return db.session.scalar(stmt)

    def create_post(self, **kwargs) -> Post:
        post = Post(**kwargs)
        db.session.add(post)
        db.session.flush()
        return post

    def list_posts(self) -> list[Post]:
        stmt = select(Post).order_by(Post.created_at.desc())
        return list(db.session.scalars(stmt))

    def list_comments(self, target_type: str, target_id: str) -> list[Comment]:
        stmt = select(Comment).where(Comment.target_type == target_type, Comment.target_id == target_id).order_by(Comment.created_at.asc())
        return list(db.session.scalars(stmt))

    def create_comment(self, **kwargs) -> Comment:
        comment = Comment(**kwargs)
        db.session.add(comment)
        db.session.flush()
        return comment

    def get_like(self, user_id: str, target_type: str, target_id: str) -> Like | None:
        stmt = select(Like).where(Like.user_id == user_id, Like.target_type == target_type, Like.target_id == target_id)
        return db.session.scalar(stmt)

    def create_like(self, **kwargs) -> Like:
        like = Like(**kwargs)
        db.session.add(like)
        db.session.flush()
        return like

    def delete_like(self, like: Like) -> None:
        db.session.delete(like)
        db.session.flush()

    def count_likes(self, target_type: str, target_id: str) -> int:
        stmt = select(func.count()).select_from(Like).where(Like.target_type == target_type, Like.target_id == target_id)
        return db.session.scalar(stmt) or 0

    def get_favorite(self, user_id: str, target_type: str, target_id: str) -> Favorite | None:
        stmt = select(Favorite).where(Favorite.user_id == user_id, Favorite.target_type == target_type, Favorite.target_id == target_id)
        return db.session.scalar(stmt)

    def create_favorite(self, **kwargs) -> Favorite:
        favorite = Favorite(**kwargs)
        db.session.add(favorite)
        db.session.flush()
        return favorite

    def delete_favorite(self, favorite: Favorite) -> None:
        db.session.delete(favorite)
        db.session.flush()

    def count_favorites(self, target_type: str, target_id: str) -> int:
        stmt = select(func.count()).select_from(Favorite).where(Favorite.target_type == target_type, Favorite.target_id == target_id)
        return db.session.scalar(stmt) or 0

    def create_report(self, **kwargs) -> Report:
        report = Report(**kwargs)
        db.session.add(report)
        db.session.flush()
        return report

    def get_block(self, user_id: str, blocked_user_id: str) -> UserBlock | None:
        stmt = select(UserBlock).where(UserBlock.user_id == user_id, UserBlock.blocked_user_id == blocked_user_id)
        return db.session.scalar(stmt)

    def create_block(self, **kwargs) -> UserBlock:
        block = UserBlock(**kwargs)
        db.session.add(block)
        db.session.flush()
        return block

    def delete_block(self, block: UserBlock) -> None:
        db.session.delete(block)
        db.session.flush()

    def block_exists_between(self, user_a: str, user_b: str) -> bool:
        stmt = select(UserBlock).where(
            or_(
                and_(UserBlock.user_id == user_a, UserBlock.blocked_user_id == user_b),
                and_(UserBlock.user_id == user_b, UserBlock.blocked_user_id == user_a),
            )
        )
        return db.session.scalar(stmt) is not None

    def active_cooldown(self, user_id: str, action_type: str, target_type: str, target_id: str, now: datetime) -> CooldownEvent | None:
        stmt = select(CooldownEvent).where(
            CooldownEvent.user_id == user_id,
            CooldownEvent.action_type == action_type,
            CooldownEvent.target_type == target_type,
            CooldownEvent.target_id == target_id,
            CooldownEvent.expires_at >= now,
        )
        return db.session.scalar(stmt)

    def recent_action_count(self, user_id: str, action_type: str, since: datetime) -> int:
        stmt = select(func.count()).select_from(CooldownEvent).where(
            CooldownEvent.user_id == user_id,
            CooldownEvent.action_type == action_type,
            CooldownEvent.created_at >= since,
        )
        return db.session.scalar(stmt) or 0

    def create_cooldown_event(self, **kwargs) -> CooldownEvent:
        event = CooldownEvent(**kwargs)
        db.session.add(event)
        db.session.flush()
        return event
