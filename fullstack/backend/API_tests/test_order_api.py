from app.extensions import db
from app.repositories.catalog_repository import CatalogRepository


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


def test_cart_add_and_get(client, app):
    csrf_token = login(client, "customer", "Customer#1234")
    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")

    add_response = client.post(
        "/api/cart/items",
        json={"dish_id": dish.id, "quantity": 2, "selected_options": {}},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert add_response.status_code == 201

    cart_response = client.get("/api/cart", headers={"Accept": "application/json"})
    assert cart_response.status_code == 200
    assert cart_response.json["data"]["items"][0]["quantity"] == 2


def test_checkout_revalidates_sold_out_state(client, app):
    csrf_token = login(client, "customer", "Customer#1234")
    with app.app_context():
        repository = CatalogRepository()
        dish = repository.get_dish_by_slug("citrus-tofu-bowl")

    client.post(
        "/api/cart/items",
        json={"dish_id": dish.id, "quantity": 1, "selected_options": {}},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )

    with app.app_context():
        dish = CatalogRepository().get_dish(dish.id)
        dish.is_sold_out = True
        db.session.add(dish)
        db.session.commit()

    response = client.post(
        "/api/orders/checkout",
        json={"checkout_key": "sold-out-checkout"},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 409
    assert response.json["code"] == "dish_sold_out"


def test_checkout_creates_order_and_get_order(client, app):
    csrf_token = login(client, "customer", "Customer#1234")
    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")

    client.post(
        "/api/cart/items",
        json={"dish_id": dish.id, "quantity": 1, "selected_options": {"addons": ["avocado"]}},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    checkout_response = client.post(
        "/api/orders/checkout",
        json={"checkout_key": "api-order-1"},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert checkout_response.status_code == 200
    order_id = checkout_response.json["data"]["id"]
    assert checkout_response.json["data"]["items"][0]["line_total_price"] == "11.50"
    assert checkout_response.json["data"]["submitted_at"].endswith("Z")

    order_response = client.get(f"/api/orders/{order_id}", headers={"Accept": "application/json"})
    assert order_response.status_code == 200
    assert order_response.json["data"]["id"] == order_id
    assert order_response.json["data"]["submitted_at"].endswith("Z")
