from app.services.errors import AppError


def test_error_contract_redacts_sensitive_details_in_json(app):
    def trigger_redacted_error():
        raise AppError(
            "validation_error",
            "Synthetic validation failure.",
            400,
            {
                "limit": 60,
                "required_roles": ["Finance Admin"],
                "nonce": "top-secret-nonce",
                "secret_key": "leak-me-not",
                "value": "discard-this",
            },
        )

    app.add_url_rule("/_test/error-redaction", "test_error_redaction", trigger_redacted_error)
    client = app.test_client()

    response = client.get("/_test/error-redaction", headers={"Accept": "application/json"})

    assert response.status_code == 400
    assert response.json == {
        "code": "validation_error",
        "message": "Synthetic validation failure.",
        "details": {
            "limit": 60,
            "required_roles": ["Finance Admin"],
            "nonce": "[redacted]",
            "secret_key": "[redacted]",
        },
    }
