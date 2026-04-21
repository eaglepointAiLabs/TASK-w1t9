import json

from app.extensions import db
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.payment_repository import PaymentRepository
from app.services.payment_security import PaymentSecurity


def fetch_csrf(client):
    response = client.get("/login")
    html = response.get_data(as_text=True)
    marker = 'name="csrf_token" value="'
    assert marker in html, "Expected /login to render a CSRF token."
    return html.split(marker)[1].split('"')[0]


def login(client, username, password):
    csrf_token = fetch_csrf(client)
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    return response.headers.get("X-CSRF-Token", csrf_token)


def create_order(client, app, checkout_key="payment-api-order"):
    customer_csrf = login(client, "customer", "Customer#1234")
    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")
    client.post(
        "/api/cart/items",
        json={"dish_id": dish.id, "quantity": 1, "selected_options": {}},
        headers={"X-CSRF-Token": customer_csrf, "Accept": "application/json"},
    )
    order_response = client.post(
        "/api/orders/checkout",
        json={"checkout_key": checkout_key},
        headers={"X-CSRF-Token": customer_csrf, "Accept": "application/json"},
    )
    return order_response.json["data"]["id"]


def signed_package(secret, key_id, reference, occurred_at, status="success"):
    payload = {"transaction_reference": reference, "status": status, "occurred_at": occurred_at}
    security = PaymentSecurity(PaymentSecurity.derive_fernet_key("tablepay-local-encryption-key"))
    return {
        "key_id": key_id,
        "signature": security.sign_payload(payload, secret),
        "transaction_reference": reference,
        "payload": payload,
        "source_name": "api-test",
    }


def test_finance_capture_and_get_payment(app):
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-capture")
    finance_csrf = login(finance_client, "finance", "Finance#12345")
    capture_response = finance_client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-pay-1",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert capture_response.status_code == 201
    payment_id = capture_response.json["data"]["id"]

    get_response = finance_client.get(f"/api/payments/{payment_id}", headers={"Accept": "application/json"})
    assert get_response.status_code == 200
    assert "encrypted_secret" not in json.dumps(get_response.json)


def test_payment_endpoints_require_authenticated_session(client):
    csrf_token = fetch_csrf(client)

    capture = client.post(
        "/api/payments/capture",
        json={"order_id": "missing", "transaction_reference": "anon-1", "capture_amount": "1.00", "status": "pending"},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert capture.status_code == 401
    assert capture.json["code"] == "authentication_required"

    verify = client.post(
        "/api/payments/callbacks/verify",
        json={},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert verify.status_code == 401
    assert verify.json["code"] == "authentication_required"

    import_response = client.post(
        "/api/payments/callbacks/import",
        json={},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert import_response.status_code == 401
    assert import_response.json["code"] == "authentication_required"

    simulate = client.post(
        "/api/payments/jsapi/simulate",
        json={"transaction_reference": "anon-1", "status": "success", "key_id": "simulator-v1"},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert simulate.status_code == 401
    assert simulate.json["code"] == "authentication_required"

    get_response = client.get("/api/payments/nonexistent", headers={"Accept": "application/json"})
    assert get_response.status_code == 401
    assert get_response.json["code"] == "authentication_required"


def test_callback_import_rejects_payload_without_transaction_reference(app):
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-no-payload-ref")
    finance_csrf = login(finance_client, "finance", "Finance#12345")
    finance_client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-pay-no-payload-ref",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )

    package_missing_payload_ref = {
        "key_id": "simulator-v1",
        "signature": "some-signature",
        "transaction_reference": "api-pay-no-payload-ref",
        "payload": {"status": "success", "occurred_at": "2026-03-28T10:00:00+00:00"},
    }

    response = finance_client.post(
        "/api/payments/callbacks/import",
        json=package_missing_payload_ref,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] in ("reference_mismatch", "validation_error")


def test_callback_verify_rejects_payload_without_transaction_reference(app):
    finance_client = app.test_client()
    finance_csrf = login(finance_client, "finance", "Finance#12345")

    package_missing_payload_ref = {
        "key_id": "simulator-v1",
        "signature": "some-signature",
        "transaction_reference": "verify-no-payload-ref",
        "payload": {"status": "success", "occurred_at": "2026-03-28T10:00:00+00:00"},
    }

    response = finance_client.post(
        "/api/payments/callbacks/verify",
        json=package_missing_payload_ref,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] in ("reference_mismatch", "validation_error")


def test_callback_verify_and_import_duplicate_behavior(app):
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-dup")
    finance_csrf = login(finance_client, "finance", "Finance#12345")
    capture_response = finance_client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-pay-dup",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    package = signed_package("simulator-secret-v1", "simulator-v1", "api-pay-dup", "2026-03-28T10:00:00+00:00")

    verify_response = finance_client.post(
        "/api/payments/callbacks/verify",
        json=package,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert verify_response.status_code == 200
    assert verify_response.json["data"]["verified"] is True

    first_import = finance_client.post(
        "/api/payments/callbacks/import",
        json=package,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    second_import = finance_client.post(
        "/api/payments/callbacks/import",
        json=package,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )

    assert first_import.status_code == 200
    assert second_import.status_code == 200
    assert first_import.json["data"]["callback_id"] == second_import.json["data"]["callback_id"]


def test_invalid_signature_rejected(app):
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-bad")
    finance_csrf = login(finance_client, "finance", "Finance#12345")
    capture_response = finance_client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-pay-bad",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert capture_response.status_code == 201
    payment_id = capture_response.json["data"]["id"]

    bad_package = signed_package("wrong-secret", "simulator-v1", "api-pay-bad", "2026-03-28T10:00:00+00:00")
    response = finance_client.post(
        "/api/payments/callbacks/import",
        json=bad_package,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )

    assert response.status_code == 409
    assert response.json["code"] == "callback_rejected"

    payment_response = finance_client.get(f"/api/payments/{payment_id}", headers={"Accept": "application/json"})
    assert payment_response.status_code == 200
    assert payment_response.json["data"]["status"] == "pending"


def test_malformed_callback_timestamp_is_rejected_and_non_mutating(app):
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-bad-ts")
    finance_csrf = login(finance_client, "finance", "Finance#12345")
    capture_response = finance_client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-pay-bad-ts",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert capture_response.status_code == 201
    payment_id = capture_response.json["data"]["id"]

    bad_timestamp_package = signed_package("simulator-secret-v1", "simulator-v1", "api-pay-bad-ts", "not-an-iso-datetime")
    response = finance_client.post(
        "/api/payments/callbacks/import",
        json=bad_timestamp_package,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )

    assert response.status_code == 409
    assert response.json["code"] == "callback_rejected"
    assert "occurred_at" in response.json["data"]["verification_message"]

    payment_response = finance_client.get(f"/api/payments/{payment_id}", headers={"Accept": "application/json"})
    assert payment_response.status_code == 200
    assert payment_response.json["data"]["status"] == "pending"


def test_list_payments_with_pagination(app):
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-list")
    finance_csrf = login(finance_client, "finance", "Finance#12345")
    finance_client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-pay-list-1",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )

    response = finance_client.get("/api/payments?page=1&page_size=1", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert len(response.json["data"]) <= 1
    assert response.json["pagination"]["page"] == 1
    assert response.json["pagination"]["page_size"] == 1
    assert "total_items" in response.json["pagination"]
    assert "has_next" in response.json["pagination"]
    assert "has_prev" in response.json["pagination"]


def test_callback_import_rejects_reference_mismatch(app):
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-mismatch")
    finance_csrf = login(finance_client, "finance", "Finance#12345")
    finance_client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-pay-mismatch",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )

    package = signed_package("simulator-secret-v1", "simulator-v1", "api-pay-mismatch", "2026-03-28T10:00:00+00:00")
    package["transaction_reference"] = "different-reference"

    response = finance_client.post(
        "/api/payments/callbacks/import",
        json=package,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "reference_mismatch"


def test_list_payments_requires_authenticated_session(client):
    response = client.get("/api/payments", headers={"Accept": "application/json"})
    assert response.status_code == 401
    assert response.json["code"] == "authentication_required"


def test_jsapi_simulator_endpoint_imports_callback(app):
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-simulator")
    finance_csrf = login(finance_client, "finance", "Finance#12345")
    capture_response = finance_client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-pay-sim",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert capture_response.status_code == 201
    payment_id = capture_response.json["data"]["id"]

    simulate_response = finance_client.post(
        "/api/payments/jsapi/simulate",
        json={"transaction_reference": "api-pay-sim", "status": "success", "key_id": "simulator-v1"},
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert simulate_response.status_code == 200
    assert simulate_response.json["data"]["import_result"]["code"] == "ok"
    assert simulate_response.json["data"]["package"]["key_id"] == "simulator-v1"

    get_response = finance_client.get(f"/api/payments/{payment_id}", headers={"Accept": "application/json"})
    assert get_response.status_code == 200
    assert get_response.json["data"]["status"] == "success"
    assert any(callback["key_id"] == "simulator-v1" for callback in get_response.json["data"]["callbacks"])


def test_rejected_callback_does_not_block_subsequent_valid_callback(app):
    """
    A rejected callback (bad signature) must not occupy the dedup slot.
    A subsequent import with a valid signature for the same reference must
    succeed and update the transaction to 'success'.
    """
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-idempotency")
    finance_csrf = login(finance_client, "finance", "Finance#12345")
    capture_response = finance_client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-pay-idempotency",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert capture_response.status_code == 201
    payment_id = capture_response.json["data"]["id"]

    # First import: rejected (wrong secret) — must not cache a rejected response
    bad_package = signed_package("wrong-secret", "simulator-v1", "api-pay-idempotency", "2026-03-28T10:00:00+00:00")
    rejected_resp = finance_client.post(
        "/api/payments/callbacks/import",
        json=bad_package,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert rejected_resp.status_code == 409
    assert rejected_resp.json["code"] == "callback_rejected"

    # Second import: valid signature — must not be blocked by the rejected entry
    valid_package = signed_package("simulator-secret-v1", "simulator-v1", "api-pay-idempotency", "2026-03-28T10:00:00+00:00")
    valid_resp = finance_client.post(
        "/api/payments/callbacks/import",
        json=valid_package,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert valid_resp.status_code == 200
    assert valid_resp.json["code"] == "ok"

    # Transaction must now reflect the successful callback
    payment_resp = finance_client.get(f"/api/payments/{payment_id}", headers={"Accept": "application/json"})
    assert payment_resp.status_code == 200
    assert payment_resp.json["data"]["status"] == "success"


def test_duplicate_transaction_reference_returns_conflict(app):
    """
    Submitting capture_payment twice with the same transaction_reference must
    return 409 duplicate_transaction — not a raw 500 IntegrityError.
    """
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-dup-ref")
    finance_csrf = login(finance_client, "finance", "Finance#12345")

    capture_payload = {
        "order_id": order_id,
        "transaction_reference": "api-pay-dup-ref",
        "capture_amount": "10.25",
        "status": "pending",
    }

    first = finance_client.post(
        "/api/payments/capture",
        json=capture_payload,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert first.status_code == 201

    second = finance_client.post(
        "/api/payments/capture",
        json=capture_payload,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert second.status_code == 409
    assert second.json["code"] == "duplicate_transaction"


def test_capture_payment_requires_transaction_reference(app):
    """
    Omitting transaction_reference must return 400 validation_error.
    """
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-no-ref")
    finance_csrf = login(finance_client, "finance", "Finance#12345")

    resp = finance_client.post(
        "/api/payments/capture",
        json={"order_id": order_id, "capture_amount": "10.25", "status": "pending"},
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json["code"] == "validation_error"



def test_revoked_signing_key_rejected_in_callback_import(app):
    """
    A callback signed with a revoked key (is_active=False) must be rejected.
    The dedup slot must not be written, so a subsequent valid submission
    from a live key can still succeed.
    """
    from sqlalchemy import select
    from app.models import GatewaySigningKey

    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-revoked-key")
    finance_csrf = login(finance_client, "finance", "Finance#12345")
    finance_client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-pay-revoked-key",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )

    # Revoke simulator-v1 in the database
    with app.app_context():
        from app.extensions import db
        key = db.session.execute(
            select(GatewaySigningKey).where(GatewaySigningKey.key_id == "simulator-v1")
        ).scalar_one()
        key.is_active = False
        db.session.commit()

    # Callback signed with the now-revoked key must be rejected
    revoked_package = signed_package(
        "simulator-secret-v1", "simulator-v1", "api-pay-revoked-key", "2026-03-28T10:00:00+00:00"
    )
    resp = finance_client.post(
        "/api/payments/callbacks/import",
        json=revoked_package,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert resp.status_code == 409
    assert resp.json["code"] == "callback_rejected"
    assert "revoked" in resp.json["data"]["verification_message"].lower()


def test_revoked_signing_key_rejected_in_callback_verify(app):
    """verify_callback_preview must also honour is_active."""
    from sqlalchemy import select
    from app.models import GatewaySigningKey

    finance_client = app.test_client()
    finance_csrf = login(finance_client, "finance", "Finance#12345")

    with app.app_context():
        from app.extensions import db
        key = db.session.execute(
            select(GatewaySigningKey).where(GatewaySigningKey.key_id == "simulator-v1")
        ).scalar_one()
        key.is_active = False
        db.session.commit()

    package = signed_package(
        "simulator-secret-v1", "simulator-v1", "api-pay-revoked-verify", "2026-03-28T10:00:00+00:00"
    )
    resp = finance_client.post(
        "/api/payments/callbacks/verify",
        json=package,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json["data"]["verified"] is False
    assert "revoked" in resp.json["data"]["message"].lower()


def test_invalid_capture_status_returns_400(app):
    """Capture with an unrecognised status must return 400 validation_error."""
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-bad-status")
    finance_csrf = login(finance_client, "finance", "Finance#12345")

    for bad_status in ("processing", "confirmed", "XYZZY"):
        resp = finance_client.post(
            "/api/payments/capture",
            json={
                "order_id": order_id,
                "transaction_reference": f"api-pay-bad-status-{bad_status}",
                "capture_amount": "10.25",
                "status": bad_status,
            },
            headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
        )
        assert resp.status_code == 400, f"Expected 400 for status={bad_status!r}, got {resp.status_code}"
        assert resp.json["code"] == "validation_error"


def test_valid_capture_statuses_accepted(app):
    """pending, success, and failed are the only accepted statuses."""
    customer_client = app.test_client()
    finance_client = app.test_client()

    order_id = create_order(customer_client, app, checkout_key="payment-api-order-valid-status")
    finance_csrf = login(finance_client, "finance", "Finance#12345")

    for idx, good_status in enumerate(("pending", "success", "failed")):
        resp = finance_client.post(
            "/api/payments/capture",
            json={
                "order_id": order_id,
                "transaction_reference": f"api-pay-valid-status-{idx}",
                "capture_amount": "10.25",
                "status": good_status,
            },
            headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
        )
        assert resp.status_code == 201, f"Expected 201 for status={good_status!r}, got {resp.status_code}"
        assert resp.json["data"]["status"] == good_status
