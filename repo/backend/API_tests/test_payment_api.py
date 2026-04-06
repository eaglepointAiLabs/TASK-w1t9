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
