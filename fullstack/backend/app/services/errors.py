from __future__ import annotations


SAFE_ERROR_DETAIL_KEYS = {
    "allowed_types",
    "expires_at",
    "limit",
    "max_bytes",
    "received_bytes",
    "required_roles",
    "retry_after_minutes",
    "retry_after_seconds",
    "row_number",
    "rules",
}

SENSITIVE_DETAIL_TOKENS = {
    "authorization",
    "client",
    "cookie",
    "credential",
    "csrf",
    "key",
    "nonce",
    "password",
    "secret",
    "session",
    "signature",
    "token",
}


def _sanitize_detail_value(value):
    if isinstance(value, dict):
        return {
            key: _sanitize_detail_value(item)
            for key, item in value.items()
            if key in SAFE_ERROR_DETAIL_KEYS and not _is_sensitive_detail_key(key)
        }
    if isinstance(value, list):
        return [_sanitize_detail_value(item) for item in value[:10]]
    if isinstance(value, tuple):
        return [_sanitize_detail_value(item) for item in value[:10]]
    if isinstance(value, str):
        return value[:160]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:160]


def _is_sensitive_detail_key(key: str) -> bool:
    normalized = key.strip().lower()
    return any(token in normalized for token in SENSITIVE_DETAIL_TOKENS)


def sanitize_error_details(details: dict | None) -> dict:
    if not isinstance(details, dict):
        return {}
    sanitized: dict = {}
    for key, value in details.items():
        if _is_sensitive_detail_key(key):
            sanitized[key] = "[redacted]"
            continue
        if key not in SAFE_ERROR_DETAIL_KEYS:
            continue
        sanitized[key] = _sanitize_detail_value(value)
    return sanitized


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
