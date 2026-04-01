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


def test_app_error_logging_redacts_sensitive_details(app, monkeypatch):
    import app.factory as app_factory
    from app.services.errors import AppError

    logged = {}

    class StubLogger:
        def info(self, event, **kwargs):
            logged["event"] = event
            logged["payload"] = kwargs

        def warning(self, event, **kwargs):
            logged["warning_event"] = event
            logged["warning_payload"] = kwargs

    monkeypatch.setattr(app_factory, "logger", StubLogger())

    @app.get("/api/test/log-safety")
    def _log_safety_route():
        raise AppError(
            "validation_error",
            "Bad request.",
            400,
            {
                "required_roles": ["Finance Admin"],
                "nonce": "super-secret-nonce",
                "token": "top-secret-token",
            },
        )

    client = app.test_client()
    response = client.get("/api/test/log-safety", headers={"Accept": "application/json"})

    assert response.status_code == 400
    assert response.json["details"]["required_roles"] == ["Finance Admin"]
    assert response.json["details"]["nonce"] == "[redacted]"
    assert response.json["details"]["token"] == "[redacted]"
    assert logged["event"] == "app.error"
    assert logged["payload"]["details"]["nonce"] == "[redacted]"
    assert logged["payload"]["details"]["token"] == "[redacted]"
