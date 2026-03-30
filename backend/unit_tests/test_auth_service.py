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


def test_register_customer_sanitizes_username_and_assigns_customer_role(app):
    service = AuthService(AuthRepository())

    user = service.register_customer(" Fresh.User_99 ", "FreshUser#12345")

    assert user.username == "fresh.user_99"
    assert AuthRepository().get_roles_by_user_id(user.id) == ["Customer"]


def test_register_customer_rejects_invalid_username(app):
    service = AuthService(AuthRepository())

    with pytest.raises(AppError) as exc:
        service.register_customer("../../etc/passwd", "SecurePass#1234")

    assert exc.value.code == "validation_error"


def test_register_customer_rejects_duplicate_username(app):
    service = AuthService(AuthRepository())

    with pytest.raises(AppError) as exc:
        service.register_customer("customer", "AnotherSecure#123")

    assert exc.value.code == "username_taken"
