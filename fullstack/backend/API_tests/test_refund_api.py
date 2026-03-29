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


def issue_nonce(client, csrf_token, purpose):
    response = client.post(
        "/api/auth/nonces",
        json={"purpose": purpose},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    return response.json["data"]["nonce"]


def test_refund_create_and_stepup_flow(app):
    from app.repositories.catalog_repository import CatalogRepository

    customer_client = app.test_client()
    finance_client = app.test_client()

    customer_csrf = login(customer_client, "customer", "Customer#1234")
    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")
    customer_client.post(
        "/api/cart/items",
        json={"dish_id": dish.id, "quantity": 1, "selected_options": {}},
        headers={"X-CSRF-Token": customer_csrf, "Accept": "application/json"},
    )
    order = customer_client.post(
        "/api/orders/checkout",
        json={"checkout_key": "refund-api-order"},
        headers={"X-CSRF-Token": customer_csrf, "Accept": "application/json"},
    ).json["data"]

    finance_csrf = login(finance_client, "finance", "Finance#12345")
    payment = finance_client.post(
        "/api/payments/capture",
        json={"order_id": order["id"], "transaction_reference": "refund-api-pay", "capture_amount": "120.25", "status": "success"},
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    ).json["data"]

    refund_response = finance_client.post(
        "/api/refunds",
        json={
            "transaction_reference": payment["transaction_reference"],
            "refund_amount": "60.00",
            "route": "offline_wechat_simulator",
            "nonce": issue_nonce(finance_client, finance_csrf, "refund:create"),
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert refund_response.status_code == 201
    assert refund_response.json["data"]["status"] == "pending_stepup"

    confirm = finance_client.post(
        f"/api/refunds/{refund_response.json['data']['id']}/confirm-stepup",
        json={"password": "Finance#12345", "nonce": issue_nonce(finance_client, finance_csrf, "refund:confirm")},
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert confirm.status_code == 200
    assert confirm.json["data"]["status"] == "approved"


def test_nonce_replay_rejected(client, app):
    finance_csrf = login(client, "finance", "Finance#12345")
    nonce = issue_nonce(client, finance_csrf, "refund:create")
    response = client.post(
        "/api/refunds",
        json={"transaction_reference": "missing", "refund_amount": "1.00", "route": "offline_wechat_simulator", "nonce": nonce},
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert response.status_code in {404, 400}
    replay = client.post(
        "/api/refunds",
        json={"transaction_reference": "missing", "refund_amount": "1.00", "route": "offline_wechat_simulator", "nonce": nonce},
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert replay.status_code == 403
    assert replay.json["code"] == "nonce_invalid"
