import pytest

from app.config import ProductionConfig


def _base_valid_config(**overrides):
    config = {
        "SECRET_KEY": "this-is-a-strong-session-secret-for-tests",
        "KEY_ENCRYPTION_SECRET": "this-is-a-strong-encryption-secret-for-tests",
        "SESSION_COOKIE_SECURE": True,
        "ALLOW_INSECURE_HTTP": False,
        "SHOW_SEEDED_CREDENTIALS": False,
        "BOOTSTRAP_SEED_DATA": False,
    }
    config.update(overrides)
    return config


def test_production_config_requires_strong_secret_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProductionConfig.validate(_base_valid_config(SECRET_KEY="short-secret"))


def test_production_config_requires_strong_encryption_secret():
    with pytest.raises(RuntimeError, match="KEY_ENCRYPTION_SECRET"):
        ProductionConfig.validate(_base_valid_config(KEY_ENCRYPTION_SECRET="too-short"))


def test_production_config_requires_secure_cookie_without_local_override():
    with pytest.raises(RuntimeError, match="SESSION_COOKIE_SECURE"):
        ProductionConfig.validate(
            _base_valid_config(SESSION_COOKIE_SECURE=False, ALLOW_INSECURE_HTTP=False)
        )


def test_production_config_allows_explicit_local_http_override():
    ProductionConfig.validate(
        _base_valid_config(SESSION_COOKIE_SECURE=False, ALLOW_INSECURE_HTTP=True)
    )


def test_production_config_rejects_committed_review_session_secret():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProductionConfig.validate(
            _base_valid_config(
                SECRET_KEY="6f5f4f92f54c4d0cb947bc65f8b2a32a_tablepay_review_session_secret"
            )
        )


def test_production_config_rejects_committed_review_encryption_secret():
    with pytest.raises(RuntimeError, match="KEY_ENCRYPTION_SECRET"):
        ProductionConfig.validate(
            _base_valid_config(
                KEY_ENCRYPTION_SECRET="1baf2af44c8748c882a33e80914dc701_tablepay_review_encryption_secret"
            )
        )


def test_production_config_rejects_dev_default_secrets():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProductionConfig.validate(
            _base_valid_config(SECRET_KEY="dev-secret-key-change-me-local-only")
        )


def test_production_config_rejects_bootstrap_seed_data():
    with pytest.raises(RuntimeError, match="BOOTSTRAP_SEED_DATA"):
        ProductionConfig.validate(_base_valid_config(BOOTSTRAP_SEED_DATA=True))


def test_production_config_rejects_show_seeded_credentials():
    with pytest.raises(RuntimeError, match="SHOW_SEEDED_CREDENTIALS"):
        ProductionConfig.validate(_base_valid_config(SHOW_SEEDED_CREDENTIALS=True))


def test_production_config_accepts_fully_hardened_config():
    ProductionConfig.validate(_base_valid_config())

