"""
API tests: malformed numeric inputs must produce 400 validation_error responses,
never 500 server errors.

Each test hits the real endpoint (Flask test client, in-memory DB, full seed) and
asserts that the validation contract is honoured — the specific error message is
confirmed where it is deterministic.

Sites covered
-------------
Catalog / dish management (manager role)
  1. stock_quantity not an integer       → validate_dish_payload / _upsert_dish
  2. sort_order not an integer           → _upsert_dish
  3. day_of_week not an integer          → validate_dish_payload / _upsert_dish
  4. day_of_week out of range [0..6]     → validate_dish_payload
  5. min_select not an integer           → validate_dish_payload / _upsert_dish
  6. max_select not an integer           → validate_dish_payload / _upsert_dish
  7. base_price not a decimal            → validate_dish_payload / parse_price

Order / cart (customer role)
  8. quantity not an integer on add      → order_service.add_cart_item
  9. quantity not an integer on update   → order_service.update_cart_item
 10. selected_options invalid JSON       → order_controller._inflate_payload
"""
from __future__ import annotations

from app.repositories.catalog_repository import CatalogRepository


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _fetch_csrf(client) -> str:
    html = client.get("/login").get_data(as_text=True)
    marker = 'name="csrf_token" value="'
    return html.split(marker)[1].split('"')[0]


def _login(client, username: str, password: str) -> str:
    csrf = _fetch_csrf(client)
    resp = client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    return resp.headers.get("X-CSRF-Token", csrf)


def _base_dish_payload(**overrides) -> dict:
    payload = {
        "name": "Test Dish",
        "base_price": "9.00",
        "category_name": "Specials",
        "availability_windows": [],
        "options": [
            {
                "name": "Size",
                "values": [{"label": "Regular", "price_delta": "0.00"}],
                "rules": [{"rule_type": "single_select_required", "is_required": True, "min_select": 1, "max_select": 1}],
            }
        ],
    }
    payload.update(overrides)
    return payload


def _assert_validation_error(response, *, status: int = 400, code: str = "validation_error") -> None:
    assert response.status_code == status, (
        f"Expected {status}, got {response.status_code}. Body: {response.get_data(as_text=True)}"
    )
    assert response.json["code"] == code


# ------------------------------------------------------------------ #
#  Catalog: integer fields on dish create                              #
# ------------------------------------------------------------------ #

def test_malformed_stock_quantity_returns_400(client):
    csrf = _login(client, "manager", "Manager#12345")
    resp = client.post(
        "/api/manager/dishes",
        json=_base_dish_payload(stock_quantity="not-a-number"),
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)
    assert "stock_quantity" in resp.json["message"].lower()


def test_malformed_sort_order_returns_400(client):
    csrf = _login(client, "manager", "Manager#12345")
    resp = client.post(
        "/api/manager/dishes",
        json=_base_dish_payload(sort_order="abc"),
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)
    assert "sort_order" in resp.json["message"].lower()


def test_malformed_base_price_returns_400(client):
    csrf = _login(client, "manager", "Manager#12345")
    resp = client.post(
        "/api/manager/dishes",
        json=_base_dish_payload(base_price="not-a-price"),
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)
    assert "base_price" in resp.json["message"].lower()


def test_malformed_day_of_week_string_returns_400(client):
    csrf = _login(client, "manager", "Manager#12345")
    payload = _base_dish_payload(
        availability_windows=[
            {"day_of_week": "monday", "start_time": "11:00", "end_time": "14:00"}
        ]
    )
    resp = client.post(
        "/api/manager/dishes",
        json=payload,
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)
    assert "day_of_week" in resp.json["message"].lower()


def test_out_of_range_day_of_week_returns_400(client):
    csrf = _login(client, "manager", "Manager#12345")
    payload = _base_dish_payload(
        availability_windows=[
            {"day_of_week": 9, "start_time": "11:00", "end_time": "14:00"}
        ]
    )
    resp = client.post(
        "/api/manager/dishes",
        json=payload,
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)
    assert "day_of_week" in resp.json["message"].lower()


def test_malformed_min_select_returns_400(client):
    csrf = _login(client, "manager", "Manager#12345")
    payload = _base_dish_payload(
        options=[
            {
                "name": "Size",
                "values": [{"label": "Regular", "price_delta": "0.00"}],
                "rules": [{"rule_type": "single_select_required", "min_select": "abc", "max_select": 1}],
            }
        ]
    )
    resp = client.post(
        "/api/manager/dishes",
        json=payload,
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)
    assert "min_select" in resp.json["message"].lower()


def test_malformed_max_select_returns_400(client):
    csrf = _login(client, "manager", "Manager#12345")
    payload = _base_dish_payload(
        options=[
            {
                "name": "Size",
                "values": [{"label": "Regular", "price_delta": "0.00"}],
                "rules": [{"rule_type": "single_select_required", "min_select": 1, "max_select": "xyz"}],
            }
        ]
    )
    resp = client.post(
        "/api/manager/dishes",
        json=payload,
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)
    assert "max_select" in resp.json["message"].lower()


# ------------------------------------------------------------------ #
#  Catalog: time format and rule_type                                   #
# ------------------------------------------------------------------ #

def test_malformed_start_time_format_returns_400(client):
    csrf = _login(client, "manager", "Manager#12345")
    payload = _base_dish_payload(
        availability_windows=[
            {"day_of_week": 1, "start_time": "not-a-time", "end_time": "14:00"}
        ]
    )
    resp = client.post(
        "/api/manager/dishes",
        json=payload,
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)


def test_malformed_end_time_format_returns_400(client):
    csrf = _login(client, "manager", "Manager#12345")
    payload = _base_dish_payload(
        availability_windows=[
            {"day_of_week": 1, "start_time": "11:00", "end_time": "99:99"}
        ]
    )
    resp = client.post(
        "/api/manager/dishes",
        json=payload,
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)


def test_missing_rule_type_returns_400(client):
    csrf = _login(client, "manager", "Manager#12345")
    payload = _base_dish_payload(
        options=[
            {
                "name": "Size",
                "values": [{"label": "Regular", "price_delta": "0.00"}],
                "rules": [{"is_required": True, "min_select": 1, "max_select": 1}],
            }
        ]
    )
    resp = client.post(
        "/api/manager/dishes",
        json=payload,
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)
    assert "rule_type" in resp.json["message"].lower()


# ------------------------------------------------------------------ #
#  Order / cart: quantity and selected_options                         #
# ------------------------------------------------------------------ #

def test_malformed_quantity_on_add_cart_item_returns_400(client, app):
    csrf = _login(client, "customer", "Customer#1234")
    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")

    resp = client.post(
        "/api/cart/items",
        json={"dish_id": dish.id, "quantity": "two", "selected_options": {}},
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)
    assert "quantity" in resp.json["message"].lower()


def test_malformed_quantity_on_update_cart_item_returns_400(client, app):
    csrf = _login(client, "customer", "Customer#1234")
    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")

    add_resp = client.post(
        "/api/cart/items",
        json={"dish_id": dish.id, "quantity": 1, "selected_options": {}},
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    assert add_resp.status_code == 201
    item_id = add_resp.json["data"]["id"]

    resp = client.patch(
        f"/api/cart/items/{item_id}",
        json={"quantity": "three"},
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)
    assert "quantity" in resp.json["message"].lower()


def test_malformed_selected_options_json_via_form_returns_400(client, app):
    csrf = _login(client, "customer", "Customer#1234")
    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")

    resp = client.post(
        "/api/cart/items",
        data={"dish_id": dish.id, "quantity": "1", "selected_options": "{not valid json}"},
        content_type="application/x-www-form-urlencoded",
        headers={"X-CSRF-Token": csrf, "Accept": "application/json"},
    )
    _assert_validation_error(resp)
    assert "selected_options" in resp.json["message"].lower()
