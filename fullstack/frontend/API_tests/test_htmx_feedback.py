from app.repositories.catalog_repository import CatalogRepository
from app.repositories.community_repository import CommunityRepository


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
    assert response.status_code == 200
    return response.headers.get("X-CSRF-Token", csrf_token)


def test_hx_login_and_logout_emit_redirect_and_toast_headers(client):
    csrf_token = fetch_csrf(client)
    login_response = client.post(
        "/auth/login",
        data={"username": "customer", "password": "Customer#1234", "csrf_token": csrf_token},
        headers={"HX-Request": "true", "X-CSRF-Token": csrf_token},
    )
    assert login_response.status_code == 200
    assert login_response.headers["X-Redirect-Location"] == "/"
    assert login_response.headers["X-Toast-Message"] == "Signed in successfully."

    csrf_token = login_response.headers["X-CSRF-Token"]
    logout_response = client.post(
        "/auth/logout",
        data={"csrf_token": csrf_token},
        headers={"HX-Request": "true", "X-CSRF-Token": csrf_token},
    )
    assert logout_response.status_code == 200
    assert logout_response.headers["X-Redirect-Location"] == "/login"
    assert logout_response.headers["X-Toast-Message"] == "Signed out."


def test_hx_authentication_failures_return_descriptive_toast_and_redirect(client, app):
    csrf_token = fetch_csrf(client)
    with app.app_context():
        post = CommunityRepository().list_posts()[0]

    response = client.post(
        "/api/community/comments",
        data={
            "target_type": "post",
            "target_id": post.id,
            "body": "This should fail while signed out.",
            "csrf_token": csrf_token,
        },
        headers={"HX-Request": "true", "X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 401
    assert response.headers["X-Toast-Message"] == "Authentication is required."
    assert response.headers["X-Redirect-Location"].endswith("/login")


def test_hx_mutations_emit_success_toasts(client, app):
    csrf_token = login(client, "customer", "Customer#1234")
    with app.app_context():
        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")
        post = CommunityRepository().list_posts()[0]

    add_to_cart = client.post(
        "/api/cart/items",
        data={
            "dish_id": dish.id,
            "quantity": "1",
            "selected_options": "{}",
            "csrf_token": csrf_token,
        },
        headers={"HX-Request": "true", "X-CSRF-Token": csrf_token},
    )
    assert add_to_cart.status_code == 201
    assert add_to_cart.headers["X-Toast-Message"] == "Item added to cart."
    assert "Checkout" in add_to_cart.get_data(as_text=True)

    like_response = client.post(
        "/api/community/likes/toggle",
        data={"target_type": "post", "target_id": post.id, "csrf_token": csrf_token},
        headers={"HX-Request": "true", "X-CSRF-Token": csrf_token},
    )
    assert like_response.status_code == 200
    assert like_response.headers["X-Toast-Message"] == "Like updated."
    assert post.title in like_response.get_data(as_text=True)


def test_hx_forbidden_page_returns_descriptive_error_feedback(client):
    csrf_token = login(client, "customer", "Customer#1234")
    response = client.get(
        "/manager/dishes",
        headers={"HX-Request": "true", "X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 403
    assert response.headers["X-Toast-Message"] == "You do not have permission to access this resource."
    assert response.headers["X-Error-Code"] == "forbidden"
