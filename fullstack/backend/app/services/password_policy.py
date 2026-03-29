from __future__ import annotations

import re

from .errors import AppError


PASSWORD_RULES = [
    (re.compile(r".{12,}"), "Password must be at least 12 characters long."),
    (re.compile(r"[A-Z]"), "Password must include at least one uppercase letter."),
    (re.compile(r"[a-z]"), "Password must include at least one lowercase letter."),
    (re.compile(r"\d"), "Password must include at least one digit."),
    (re.compile(r"[^A-Za-z0-9]"), "Password must include at least one special character."),
]


def validate_password_complexity(password: str) -> None:
    errors = [message for pattern, message in PASSWORD_RULES if not pattern.search(password)]
    if errors:
        raise AppError(
            code="password_policy_failed",
            message="Password does not meet complexity requirements.",
            status_code=400,
            details={"rules": errors},
        )
