from __future__ import annotations

import os
from base64 import urlsafe_b64encode
from hashlib import sha256
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
INSTANCE_DIR = BASE_DIR / "instance"
DEFAULT_SQLITE_PATH = DATA_DIR / "tablepay.db"
UPLOAD_DIR = DATA_DIR / "uploads"
BACKUP_DIR = DATA_DIR / "backups"
RESTORE_DIR = DATA_DIR / "restore-tests"


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() == "true"


def _is_weak_secret(secret: str | None) -> bool:
    if secret is None:
        return True
    normalized = secret.strip()
    if len(normalized) < 32:
        return True
    lowered = normalized.lower()
    return lowered in {
        "dev-secret-key-change-me",
        "tablepay-local-encryption-key",
        "dev-local-encryption-secret-change-me",
        "test-secret-key-for-tablepay-suite",
        "test-encryption-secret-for-tablepay-suite",
    }


class Config:
    APP_NAME = "TablePay"
    SECRET_KEY = None
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}",
    )
    SESSION_COOKIE_NAME = "tablepay_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    ALLOW_INSECURE_HTTP = False
    LOCKOUT_WINDOW_MINUTES = 15
    LOCKOUT_MAX_ATTEMPTS = 10
    SESSION_TTL_HOURS = 12
    CSRF_TTL_HOURS = 12
    NONCE_TTL_MINUTES = 5
    JSON_SORT_KEYS = False
    UPLOAD_DIR = UPLOAD_DIR
    BACKUP_DIR = BACKUP_DIR
    RESTORE_DIR = RESTORE_DIR
    KEY_ENCRYPTION_SECRET = None
    MENU_CACHE_TTL_SECONDS = 60
    RATE_LIMIT_PER_MINUTE = 60
    CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
    CIRCUIT_BREAKER_WINDOW_SECONDS = 60
    CIRCUIT_BREAKER_RESET_SECONDS = 120
    BACKUP_RETENTION_DAYS = 14

    @staticmethod
    def init_app() -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        RESTORE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def runtime_overrides(cls) -> dict[str, object]:
        return {}

    @classmethod
    def validate(cls, config: dict) -> None:
        return None

    @classmethod
    def encryption_key(cls) -> bytes:
        return urlsafe_b64encode(sha256(cls.KEY_ENCRYPTION_SECRET.encode("utf-8")).digest())


class DevelopmentConfig(Config):
    ENV_NAME = "development"
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me-local-only")
    KEY_ENCRYPTION_SECRET = os.getenv("KEY_ENCRYPTION_SECRET", "dev-local-encryption-secret-change-me")
    SESSION_COOKIE_SECURE = _env_flag("SESSION_COOKIE_SECURE", "false")
    ALLOW_INSECURE_HTTP = _env_flag("ALLOW_INSECURE_HTTP", "true")


class TestConfig(Config):
    ENV_NAME = "test"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key-for-tablepay-suite"
    KEY_ENCRYPTION_SECRET = "test-encryption-secret-for-tablepay-suite"
    SESSION_COOKIE_SECURE = False
    ALLOW_INSECURE_HTTP = True


class ProductionConfig(Config):
    ENV_NAME = "production"
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"

    @classmethod
    def runtime_overrides(cls) -> dict[str, object]:
        return {
            "SECRET_KEY": os.getenv("SECRET_KEY"),
            "KEY_ENCRYPTION_SECRET": os.getenv("KEY_ENCRYPTION_SECRET"),
            "SESSION_COOKIE_SECURE": _env_flag("SESSION_COOKIE_SECURE", "true"),
            "ALLOW_INSECURE_HTTP": _env_flag("ALLOW_INSECURE_HTTP", "false"),
        }

    @classmethod
    def validate(cls, config: dict) -> None:
        if _is_weak_secret(config.get("SECRET_KEY")):
            raise RuntimeError("Production SECRET_KEY must be set to a non-default value of at least 32 characters.")
        if _is_weak_secret(config.get("KEY_ENCRYPTION_SECRET")):
            raise RuntimeError(
                "Production KEY_ENCRYPTION_SECRET must be set to a non-default value of at least 32 characters."
            )
        if not config.get("SESSION_COOKIE_SECURE") and not config.get("ALLOW_INSECURE_HTTP"):
            raise RuntimeError(
                "Production requires SESSION_COOKIE_SECURE=true. Set ALLOW_INSECURE_HTTP=true only for trusted local HTTP review."
            )


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "test": TestConfig,
    "production": ProductionConfig,
}
