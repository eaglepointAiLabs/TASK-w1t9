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


def test_public_shell_redirects_to_login_and_login_page_renders(client):
    home = client.get("/", follow_redirects=False)
    assert home.status_code == 302
    assert home.headers["Location"].endswith("/login")

    login_page = client.get("/login")
    html = login_page.get_data(as_text=True)
    assert login_page.status_code == 200
    assert "Sign in to the TablePay control room" in html
    assert 'name="csrf_token"' in html


def test_authenticated_user_is_redirected_away_from_login(client):
    login(client, "customer", "Customer#1234")

    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_customer_pages_render_and_privileged_pages_are_forbidden(client):
    login(client, "customer", "Customer#1234")

    for path in ["/menu", "/cart", "/community"]:
        response = client.get(path)
        assert response.status_code == 200, path

    for path in ["/manager/dishes", "/finance/payments", "/finance/reconciliation", "/finance/refunds", "/moderation", "/admin/roles"]:
        response = client.get(path)
        assert response.status_code == 403, path


def test_role_specific_pages_render_for_authorized_roles(app):
    manager_client = app.test_client()
    finance_client = app.test_client()
    moderator_client = app.test_client()

    login(manager_client, "manager", "Manager#12345")
    assert manager_client.get("/manager/dishes").status_code == 200

    login(finance_client, "finance", "Finance#12345")
    for path in ["/finance/payments", "/finance/reconciliation", "/finance/refunds", "/admin/roles"]:
        response = finance_client.get(path)
        assert response.status_code == 200, path

    login(moderator_client, "moderator", "Moderator#123")
    assert moderator_client.get("/moderation").status_code == 200
    assert moderator_client.get("/admin/roles").status_code == 403
