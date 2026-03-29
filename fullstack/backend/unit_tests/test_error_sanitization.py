from app.services.errors import sanitize_error_details


def test_error_detail_sanitizer_keeps_safe_fields_only():
    details = {
        "limit": 60,
        "rules": ["Password must include a digit."],
        "required_roles": ["Finance Admin"],
        "nonce": "should-not-leak",
        "secret_key": "also-hidden",
        "value": "untrusted-user-input",
        "nested": {"password": "bad"},
    }

    sanitized = sanitize_error_details(details)

    assert sanitized == {
        "limit": 60,
        "rules": ["Password must include a digit."],
        "required_roles": ["Finance Admin"],
        "nonce": "[redacted]",
        "secret_key": "[redacted]",
    }


def test_error_detail_sanitizer_limits_list_and_string_size():
    details = {
        "rules": ["x" * 300 for _ in range(12)],
    }

    sanitized = sanitize_error_details(details)

    assert len(sanitized["rules"]) == 10
    assert len(sanitized["rules"][0]) == 160
