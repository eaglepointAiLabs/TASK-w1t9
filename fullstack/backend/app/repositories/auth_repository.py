from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import AuthAttempt, CsrfToken, Nonce, Role, Session, User, UserRole
from app.services.time_utils import utc_now_naive


class AuthRepository:
    def get_user_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return db.session.scalar(stmt)

    def get_roles_by_user_id(self, user_id: str) -> list[str]:
        stmt = (
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        return list(db.session.scalars(stmt))

    def create_attempt(self, username: str, was_success: bool, ip_address: str | None) -> AuthAttempt:
        attempt = AuthAttempt(
            username=username.lower().strip(),
            attempted_at=utc_now_naive(),
            was_success=was_success,
            ip_address=ip_address,
        )
        db.session.add(attempt)
        db.session.flush()
        return attempt

    def failed_attempts_since(self, username: str, since: datetime) -> int:
        stmt = select(AuthAttempt).where(
            AuthAttempt.username == username.lower().strip(),
            AuthAttempt.was_success.is_(False),
            AuthAttempt.attempted_at >= since,
        )
        return len(list(db.session.scalars(stmt)))

    def create_session(self, user_id: str, session_token: str, expires_at: datetime) -> Session:
        session = Session(user_id=user_id, session_token=session_token, expires_at=expires_at)
        db.session.add(session)
        db.session.flush()
        return session

    def get_session(self, session_token: str) -> Session | None:
        stmt = select(Session).where(Session.session_token == session_token)
        return db.session.scalar(stmt)

    def revoke_session(self, session: Session) -> None:
        session.revoked_at = utc_now_naive()
        db.session.add(session)

    def create_csrf_token(
        self,
        client_id: str,
        token: str,
        expires_at: datetime,
        session_id: str | None = None,
    ) -> CsrfToken:
        csrf = CsrfToken(
            client_id=client_id,
            session_id=session_id,
            token=token,
            expires_at=expires_at,
        )
        db.session.add(csrf)
        db.session.flush()
        return csrf

    def get_valid_csrf_token(self, token: str, client_id: str) -> CsrfToken | None:
        stmt = select(CsrfToken).where(
            CsrfToken.token == token,
            CsrfToken.client_id == client_id,
            CsrfToken.expires_at >= utc_now_naive(),
        )
        return db.session.scalar(stmt)

    def delete_csrf_tokens_for_client(self, client_id: str) -> None:
        stmt = select(CsrfToken).where(CsrfToken.client_id == client_id)
        for item in db.session.scalars(stmt):
            db.session.delete(item)

    def create_nonce(self, session_id: str, purpose: str, value: str, expires_at: datetime) -> Nonce:
        nonce = Nonce(session_id=session_id, purpose=purpose, value=value, expires_at=expires_at)
        db.session.add(nonce)
        db.session.flush()
        return nonce

    def get_valid_nonce(self, session_id: str, purpose: str, value: str) -> Nonce | None:
        stmt = select(Nonce).where(
            Nonce.session_id == session_id,
            Nonce.purpose == purpose,
            Nonce.value == value,
            Nonce.expires_at >= utc_now_naive(),
            Nonce.consumed_at.is_(None),
        )
        return db.session.scalar(stmt)

    def consume_nonce(self, nonce: Nonce) -> None:
        nonce.consumed_at = utc_now_naive()
        db.session.add(nonce)
