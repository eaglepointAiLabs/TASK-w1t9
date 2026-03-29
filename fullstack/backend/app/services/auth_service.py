from __future__ import annotations

from datetime import timedelta
from secrets import token_urlsafe

import structlog

from app.extensions import bcrypt, db
from app.models import Session, User
from app.repositories.auth_repository import AuthRepository
from app.services.errors import AppError
from app.services.password_policy import validate_password_complexity
from app.services.time_utils import utc_now_naive


logger = structlog.get_logger(__name__)


class AuthService:
    def __init__(self, repository: AuthRepository) -> None:
        self.repository = repository

    def issue_csrf_token(self, client_id: str, session_id: str | None = None, ttl_hours: int = 12) -> str:
        self.repository.delete_csrf_tokens_for_client(client_id)
        token = token_urlsafe(32)
        self.repository.create_csrf_token(
            client_id=client_id,
            token=token,
            session_id=session_id,
            expires_at=utc_now_naive() + timedelta(hours=ttl_hours),
        )
        db.session.commit()
        return token

    def validate_csrf(self, token: str | None, client_id: str | None) -> None:
        if not token or not client_id:
            raise AppError("csrf_required", "CSRF token is required.", 403)
        csrf = self.repository.get_valid_csrf_token(token, client_id)
        if csrf is None:
            raise AppError("csrf_invalid", "CSRF token is invalid or expired.", 403)

    def login(
        self,
        username: str,
        password: str,
        ip_address: str | None,
        session_ttl_hours: int,
        lockout_window_minutes: int,
        lockout_max_attempts: int,
    ) -> tuple[User, Session]:
        normalized = username.lower().strip()
        if not normalized or not password:
            raise AppError("invalid_credentials", "Username and password are required.", 400)

        window_start = utc_now_naive() - timedelta(minutes=lockout_window_minutes)
        failures = self.repository.failed_attempts_since(normalized, window_start)
        if failures >= lockout_max_attempts:
            logger.info("auth.lockout", username=normalized, ip_address=ip_address)
            raise AppError(
                "account_locked",
                "Too many failed login attempts. Try again later.",
                423,
                details={"retry_after_minutes": lockout_window_minutes},
            )

        user = self.repository.get_user_by_username(normalized)
        if user is None or not bcrypt.check_password_hash(user.password_hash, password):
            self.repository.create_attempt(normalized, False, ip_address)
            db.session.commit()
            logger.info("auth.login_failed", username=normalized, ip_address=ip_address)
            raise AppError("invalid_credentials", "Invalid username or password.", 401)

        self.repository.create_attempt(normalized, True, ip_address)
        session = self.repository.create_session(
            user_id=user.id,
            session_token=token_urlsafe(48),
            expires_at=utc_now_naive() + timedelta(hours=session_ttl_hours),
        )
        db.session.commit()
        logger.info("auth.login_success", username=normalized, user_id=user.id, ip_address=ip_address)
        return user, session

    def logout(self, current_session: Session | None) -> None:
        if current_session is None:
            return
        self.repository.revoke_session(current_session)
        db.session.commit()
        logger.info("auth.logout", user_id=current_session.user_id, session_id=current_session.id)

    def get_current_user(self, session_token: str | None) -> tuple[User | None, Session | None, list[str]]:
        if not session_token:
            return None, None, []

        session = self.repository.get_session(session_token)
        now = utc_now_naive()
        if session is None or session.revoked_at is not None or session.expires_at < now:
            return None, None, []

        user = session.user
        roles = self.repository.get_roles_by_user_id(user.id)
        return user, session, roles

    def create_user_with_password(self, username: str, password: str) -> User:
        validate_password_complexity(password)
        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        user = User(username=username.lower().strip(), password_hash=password_hash)
        db.session.add(user)
        db.session.flush()
        return user

    def issue_nonce(self, session_id: str, purpose: str, ttl_minutes: int) -> str:
        nonce_value = token_urlsafe(32)
        self.repository.create_nonce(
            session_id=session_id,
            purpose=purpose,
            value=nonce_value,
            expires_at=utc_now_naive() + timedelta(minutes=ttl_minutes),
        )
        db.session.commit()
        return nonce_value

    def consume_nonce(self, session_id: str | None, purpose: str, value: str | None) -> None:
        if not session_id or not value:
            raise AppError("nonce_required", "A valid nonce is required.", 403)
        nonce = self.repository.get_valid_nonce(session_id, purpose, value)
        if nonce is None:
            raise AppError("nonce_invalid", "Nonce is invalid, expired, or already used.", 403)
        self.repository.consume_nonce(nonce)
        db.session.commit()
