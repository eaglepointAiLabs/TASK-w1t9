"""
Regression suite for strict request-shape validation on mutation endpoints.

A non-object JSON body (array, string, null, number) must be rejected with
HTTP 400 "validation_error" before the service layer. Previously, such
bodies reached controller/service code and raised an uncaught AttributeError
that surfaced as HTTP 500.
"""

from __future__ import annotations


def fetch_csrf(client):
    response = client.get("/login")
    html = response.get_data(as_text=True)
    marker = 'name="csrf_token" value="'
    return html.split(marker)[1].split('"')[0]


def login(client, username, password):
    csrf_token = fetch_csrf(client)
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    return response.headers.get("X-CSRF-Token", csrf_token)


def test_add_cart_item_rejects_json_array_body(client):
    csrf_token = login(client, "customer", "Customer#1234")
    response = client.post(
        "/api/cart/items",
        json=[],
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "validation_error"


def test_update_cart_item_rejects_non_dict_selected_options(client, app):
    from app.repositories.catalog_repository import CatalogRepository

    csrf_token = login(client, "customer", "Customer#1234")
    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")

    created = client.post(
        "/api/cart/items",
        json={"dish_id": dish.id, "quantity": 1, "selected_options": {}},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert created.status_code == 201
    item_id = created.json["data"]["id"]

    response = client.patch(
        f"/api/cart/items/{item_id}",
        json={"quantity": 2, "selected_options": ["not", "a", "dict"]},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "validation_error"


def test_checkout_rejects_json_array_body(client):
    csrf_token = login(client, "customer", "Customer#1234")
    response = client.post(
        "/api/orders/checkout",
        json=[],
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "validation_error"


def test_manager_bulk_update_rejects_json_array_body(client):
    csrf_token = login(client, "manager", "Manager#12345")
    response = client.post(
        "/api/manager/dishes/bulk-update",
        json=[],
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "validation_error"


def test_manager_create_dish_rejects_scalar_options_field(client):
    csrf_token = login(client, "manager", "Manager#12345")
    response = client.post(
        "/api/manager/dishes",
        json={"name": "Bad Shape", "base_price": "5.00", "options": 42},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "validation_error"


def test_toggle_like_rejects_json_array_body(client):
    csrf_token = login(client, "customer", "Customer#1234")
    response = client.post(
        "/api/community/likes/toggle",
        json=[],
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "validation_error"


def test_create_comment_rejects_json_array_body(client):
    csrf_token = login(client, "customer", "Customer#1234")
    response = client.post(
        "/api/community/comments",
        json=[],
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "validation_error"


def test_payment_capture_rejects_json_array_body(client):
    csrf_token = login(client, "finance", "Finance#12345")
    response = client.post(
        "/api/payments/capture",
        json=[],
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "validation_error"


def test_callback_import_rejects_json_array_body(client):
    csrf_token = login(client, "finance", "Finance#12345")
    response = client.post(
        "/api/payments/callbacks/import",
        json=[],
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "validation_error"


def test_callback_verify_rejects_json_array_body(client):
    csrf_token = login(client, "finance", "Finance#12345")
    response = client.post(
        "/api/payments/callbacks/verify",
        json=[],
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "validation_error"


def test_reconciliation_resolve_rejects_json_array_body(client):
    # The payload shape check runs before the exception lookup, so the
    # endpoint can reject a malformed body without a real exception id.
    csrf_token = login(client, "finance", "Finance#12345")
    response = client.post(
        "/api/finance/reconciliation/exceptions/any-placeholder-id/resolve",
        json=[],
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "validation_error"


def test_reconciliation_import_rejects_json_array_body(client):
    csrf_token = login(client, "finance", "Finance#12345")
    response = client.post(
        "/api/finance/reconciliation/import",
        json=[],
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["code"] == "validation_error"
