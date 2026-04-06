import pytest

from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import AuthService
from app.services.errors import AppError


def test_login_success_creates_session(app):
    service = AuthService(AuthRepository())
    user, session = service.login("customer", "Customer#1234", "127.0.0.1", 12, 15, 10)

    assert user.username == "customer"
    assert session.session_token


def test_login_rejects_empty_credentials(app):
    service = AuthService(AuthRepository())

    with pytest.raises(AppError) as exc:
        service.login("", "Customer#1234", "127.0.0.1", 12, 15, 10)
    assert exc.value.code == "invalid_credentials"

    with pytest.raises(AppError) as exc:
        service.login("customer", "", "127.0.0.1", 12, 15, 10)
    assert exc.value.code == "invalid_credentials"


def test_login_rejects_wrong_password(app):
    service = AuthService(AuthRepository())

    with pytest.raises(AppError) as exc:
        service.login("customer", "WrongPassword#1234", "127.0.0.1", 12, 15, 10)
    assert exc.value.code == "invalid_credentials"
    assert exc.value.status_code == 401


def test_login_rejects_nonexistent_user(app):
    service = AuthService(AuthRepository())

    with pytest.raises(AppError) as exc:
        service.login("nonexistent_user", "Password#1234", "127.0.0.1", 12, 15, 10)
    assert exc.value.code == "invalid_credentials"


def test_lockout_after_ten_failures(app):
    service = AuthService(AuthRepository())
    for _ in range(10):
        with pytest.raises(AppError):
            service.login("customer", "wrong-password", "127.0.0.1", 12, 15, 10)

    with pytest.raises(AppError) as exc:
        service.login("customer", "wrong-password", "127.0.0.1", 12, 15, 10)

    assert exc.value.code == "account_locked"
    assert exc.value.status_code == 423


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


def test_register_customer_rejects_short_username(app):
    service = AuthService(AuthRepository())

    with pytest.raises(AppError) as exc:
        service.register_customer("ab", "SecurePass#1234")
    assert exc.value.code == "validation_error"


def test_register_customer_rejects_duplicate_username(app):
    service = AuthService(AuthRepository())

    with pytest.raises(AppError) as exc:
        service.register_customer("customer", "AnotherSecure#123")

    assert exc.value.code == "username_taken"


def test_session_validation_returns_user_and_roles(app):
    service = AuthService(AuthRepository())
    user, session = service.login("customer", "Customer#1234", "127.0.0.1", 12, 15, 10)

    found_user, found_session, roles = service.get_current_user(session.session_token)

    assert found_user.id == user.id
    assert found_session.id == session.id
    assert "Customer" in roles


def test_session_validation_returns_none_for_invalid_token(app):
    service = AuthService(AuthRepository())
    user, session, roles = service.get_current_user("invalid-token")

    assert user is None
    assert session is None
    assert roles == []


def test_session_validation_returns_none_for_empty_token(app):
    service = AuthService(AuthRepository())
    user, session, roles = service.get_current_user(None)

    assert user is None
    assert session is None
    assert roles == []


def test_session_validation_rejects_revoked_session(app):
    service = AuthService(AuthRepository())
    user, session = service.login("customer", "Customer#1234", "127.0.0.1", 12, 15, 10)
    service.logout(session)

    found_user, found_session, roles = service.get_current_user(session.session_token)
    assert found_user is None
    assert roles == []


def test_csrf_issue_and_validate(app):
    service = AuthService(AuthRepository())
    token = service.issue_csrf_token("client-id-1")

    assert token is not None
    service.validate_csrf(token, "client-id-1")


def test_csrf_rejects_missing_token(app):
    service = AuthService(AuthRepository())

    with pytest.raises(AppError) as exc:
        service.validate_csrf(None, "client-id-1")
    assert exc.value.code == "csrf_required"


def test_csrf_rejects_invalid_token(app):
    service = AuthService(AuthRepository())

    with pytest.raises(AppError) as exc:
        service.validate_csrf("invalid-csrf-token", "client-id-1")
    assert exc.value.code == "csrf_invalid"


def test_csrf_rejects_wrong_client_id(app):
    service = AuthService(AuthRepository())
    token = service.issue_csrf_token("client-id-1")

    with pytest.raises(AppError) as exc:
        service.validate_csrf(token, "wrong-client-id")
    assert exc.value.code == "csrf_invalid"


def test_nonce_issue_and_consume(app):
    service = AuthService(AuthRepository())
    _user, session = service.login("finance", "Finance#12345", "127.0.0.1", 12, 15, 10)

    nonce = service.issue_nonce(session.id, "refund:create", 5)
    assert nonce is not None

    service.consume_nonce(session.id, "refund:create", nonce)


def test_nonce_rejects_replay(app):
    service = AuthService(AuthRepository())
    _user, session = service.login("finance", "Finance#12345", "127.0.0.1", 12, 15, 10)
    nonce = service.issue_nonce(session.id, "refund:create", 5)
    service.consume_nonce(session.id, "refund:create", nonce)

    with pytest.raises(AppError) as exc:
        service.consume_nonce(session.id, "refund:create", nonce)
    assert exc.value.code == "nonce_invalid"


def test_nonce_rejects_missing_value(app):
    service = AuthService(AuthRepository())

    with pytest.raises(AppError) as exc:
        service.consume_nonce("session-id", "refund:create", None)
    assert exc.value.code == "nonce_required"


def test_nonce_rejects_wrong_purpose(app):
    service = AuthService(AuthRepository())
    _user, session = service.login("finance", "Finance#12345", "127.0.0.1", 12, 15, 10)
    nonce = service.issue_nonce(session.id, "refund:create", 5)

    with pytest.raises(AppError) as exc:
        service.consume_nonce(session.id, "wrong:purpose", nonce)
    assert exc.value.code == "nonce_invalid"


def test_logout_revokes_session(app):
    service = AuthService(AuthRepository())
    _user, session = service.login("customer", "Customer#1234", "127.0.0.1", 12, 15, 10)

    service.logout(session)

    user, found_session, roles = service.get_current_user(session.session_token)
    assert user is None


def test_logout_none_session_is_noop(app):
    service = AuthService(AuthRepository())
    service.logout(None)
