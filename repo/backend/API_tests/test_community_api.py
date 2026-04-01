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


def test_like_favorite_comment_and_report_validation(client, app):
    from app.repositories.community_repository import CommunityRepository

    csrf_token = login(client, "customer", "Customer#1234")
    with app.app_context():
        post = CommunityRepository().list_posts()[0]

    like = client.post("/api/community/likes/toggle", json={"target_type": "post", "target_id": post.id}, headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"})
    assert like.status_code == 200
    favorite = client.post("/api/community/favorites/toggle", json={"target_type": "post", "target_id": post.id}, headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"})
    assert favorite.status_code == 200
    comment = client.post("/api/community/comments", json={"target_type": "post", "target_id": post.id, "body": "Nice review"}, headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"})
    assert comment.status_code == 201
    bad_report = client.post("/api/community/reports", json={"target_type": "post", "target_id": post.id, "reason_code": "bad"}, headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"})
    assert bad_report.status_code == 400


def test_block_and_unblock_behavior(client, app):
    from app.repositories.auth_repository import AuthRepository

    csrf_token = login(client, "customer", "Customer#1234")
    with app.app_context():
        moderator = AuthRepository().get_user_by_username("moderator")
    block = client.post("/api/community/blocks", json={"blocked_user_id": moderator.id}, headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"})
    assert block.status_code == 201
    unblock = client.delete(f"/api/community/blocks/{moderator.id}", headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"})
    assert unblock.status_code == 200


def test_unblock_rejects_cross_user_block_access(app):
    customer_client = app.test_client()
    manager_client = app.test_client()

    customer_csrf = login(customer_client, "customer", "Customer#1234")
    manager_csrf = login(manager_client, "manager", "Manager#12345")

    from app.repositories.auth_repository import AuthRepository

    with app.app_context():
        moderator = AuthRepository().get_user_by_username("moderator")

    block = customer_client.post(
        "/api/community/blocks",
        json={"blocked_user_id": moderator.id},
        headers={"X-CSRF-Token": customer_csrf, "Accept": "application/json"},
    )
    assert block.status_code == 201

    denied = manager_client.delete(
        f"/api/community/blocks/{moderator.id}",
        headers={"X-CSRF-Token": manager_csrf, "Accept": "application/json"},
    )
    assert denied.status_code == 404
    assert denied.json["code"] == "not_found"
