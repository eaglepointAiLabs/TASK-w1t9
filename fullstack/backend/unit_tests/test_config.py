import pytest

from app.config import ProductionConfig


def test_production_config_requires_strong_secret_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProductionConfig.validate(
            {
                "SECRET_KEY": "short-secret",
                "KEY_ENCRYPTION_SECRET": "this-is-a-strong-encryption-secret-for-tests",
                "SESSION_COOKIE_SECURE": True,
                "ALLOW_INSECURE_HTTP": False,
            }
        )


def test_production_config_requires_strong_encryption_secret():
    with pytest.raises(RuntimeError, match="KEY_ENCRYPTION_SECRET"):
        ProductionConfig.validate(
            {
                "SECRET_KEY": "this-is-a-strong-session-secret-for-tests",
                "KEY_ENCRYPTION_SECRET": "too-short",
                "SESSION_COOKIE_SECURE": True,
                "ALLOW_INSECURE_HTTP": False,
            }
        )


def test_production_config_requires_secure_cookie_without_local_override():
    with pytest.raises(RuntimeError, match="SESSION_COOKIE_SECURE"):
        ProductionConfig.validate(
            {
                "SECRET_KEY": "this-is-a-strong-session-secret-for-tests",
                "KEY_ENCRYPTION_SECRET": "this-is-a-strong-encryption-secret-for-tests",
                "SESSION_COOKIE_SECURE": False,
                "ALLOW_INSECURE_HTTP": False,
            }
        )


def test_production_config_allows_explicit_local_http_override():
    ProductionConfig.validate(
        {
            "SECRET_KEY": "this-is-a-strong-session-secret-for-tests",
            "KEY_ENCRYPTION_SECRET": "this-is-a-strong-encryption-secret-for-tests",
            "SESSION_COOKIE_SECURE": False,
            "ALLOW_INSECURE_HTTP": True,
        }
    )
