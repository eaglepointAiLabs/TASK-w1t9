import pytest

from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import AuthService
from app.services.errors import AppError


def test_login_success_creates_session(app):
    service = AuthService(AuthRepository())
    user, session = service.login("customer", "Customer#1234", "127.0.0.1", 12, 15, 10)

    assert user.username == "customer"
    assert session.session_token


def test_lockout_after_ten_failures(app):
    service = AuthService(AuthRepository())
    for _ in range(10):
        with pytest.raises(AppError):
            service.login("customer", "wrong-password", "127.0.0.1", 12, 15, 10)

    with pytest.raises(AppError) as exc:
        service.login("customer", "wrong-password", "127.0.0.1", 12, 15, 10)

    assert exc.value.code == "account_locked"
