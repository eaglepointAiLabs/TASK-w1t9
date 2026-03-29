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
    finance_client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-pay-bad",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )

    bad_package = signed_package("wrong-secret", "simulator-v1", "api-pay-bad", "2026-03-28T10:00:00+00:00")
    response = finance_client.post(
        "/api/payments/callbacks/import",
        json=bad_package,
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )

    assert response.status_code == 409
    assert response.json["code"] == "callback_rejected"
