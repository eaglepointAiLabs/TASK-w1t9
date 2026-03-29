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


def test_moderator_permission_boundary_and_decision(app):
    from app.repositories.community_repository import CommunityRepository

    customer_client = app.test_client()
    moderator_client = app.test_client()

    customer_csrf = login(customer_client, "customer", "Customer#1234")
    with app.app_context():
        post = CommunityRepository().list_posts()[0]
    customer_client.post(
        "/api/community/reports",
        json={"target_type": "post", "target_id": post.id, "reason_code": "abuse", "details": "needs review"},
        headers={"X-CSRF-Token": customer_csrf, "Accept": "application/json"},
    )

    customer_queue = customer_client.get("/api/moderation/queue", headers={"Accept": "application/json"})
    assert customer_queue.status_code == 403

    moderator_csrf = login(moderator_client, "moderator", "Moderator#123")
    queue = moderator_client.get("/api/moderation/queue", headers={"Accept": "application/json"})
    assert queue.status_code == 200
    item_id = queue.json["data"][0]["id"]

    bad_decision = moderator_client.post(
        f"/api/moderation/items/{item_id}/decision",
        json={"outcome": "remove", "reason_code": "", "operator_notes": ""},
        headers={"X-CSRF-Token": moderator_csrf, "Accept": "application/json"},
    )
    assert bad_decision.status_code == 400

    good_decision = moderator_client.post(
        f"/api/moderation/items/{item_id}/decision",
        json={"outcome": "remove", "reason_code": "abuse_content", "operator_notes": "Confirmed abusive content."},
        headers={"X-CSRF-Token": moderator_csrf, "Accept": "application/json"},
    )
    assert good_decision.status_code == 200

    history = moderator_client.get(f"/api/moderation/items/{item_id}/history", headers={"Accept": "application/json"})
    assert history.status_code == 200
    assert history.json["data"]["history"][0]["outcome"] == "remove"


def test_role_change_nonce_requirement(client):
    finance_csrf = login(client, "finance", "Finance#12345")
    missing_nonce = client.post(
        "/api/admin/roles/change",
        json={"target_username": "customer", "role_name": "Moderator", "action": "grant"},
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert missing_nonce.status_code == 403

    granted = client.post(
        "/api/admin/roles/change",
        json={
            "target_username": "customer",
            "role_name": "Moderator",
            "action": "grant",
            "nonce": issue_nonce(client, finance_csrf, "admin:role_change"),
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert granted.status_code == 200


def test_moderator_cannot_change_roles(client):
    moderator_csrf = login(client, "moderator", "Moderator#123")
    denied = client.post(
        "/api/admin/roles/change",
        json={
            "target_username": "customer",
            "role_name": "Moderator",
            "action": "grant",
            "nonce": issue_nonce(client, moderator_csrf, "admin:role_change"),
        },
        headers={"X-CSRF-Token": moderator_csrf, "Accept": "application/json"},
    )
    assert denied.status_code == 403
    assert denied.json["code"] == "forbidden"
