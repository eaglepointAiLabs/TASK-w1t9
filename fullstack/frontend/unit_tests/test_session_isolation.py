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
    assert response.status_code == 200
    return response.headers.get("X-CSRF-Token", csrf_token)


def logout(client, csrf_token):
    response = client.post(
        "/auth/logout",
        json={},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert response.status_code == 200


def test_logout_returns_browser_session_to_login_boundary(client):
    csrf_token = login(client, "customer", "Customer#1234")
    logout(client, csrf_token)

    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert 'name="csrf_token"' in login_page.get_data(as_text=True)

    protected = client.get("/cart", follow_redirects=False)
    assert protected.status_code == 302
    assert protected.headers["Location"].endswith("/login")


def test_single_browser_session_can_switch_users_without_stale_privileges(client):
    customer_csrf = login(client, "customer", "Customer#1234")
    assert client.get("/finance/payments").status_code == 403

    logout(client, customer_csrf)

    finance_csrf = login(client, "finance", "Finance#12345")
    finance_home = client.get("/")
    finance_html = finance_home.get_data(as_text=True)

    assert finance_home.status_code == 200
    assert "finance" in finance_html
    assert "customer" not in finance_html
    assert client.get("/finance/payments").status_code == 200
    assert client.get("/manager/dishes").status_code == 403

    logout(client, finance_csrf)


def test_parallel_browser_sessions_keep_role_access_isolated(app):
    customer_client = app.test_client()
    finance_client = app.test_client()

    login(customer_client, "customer", "Customer#1234")
    login(finance_client, "finance", "Finance#12345")

    assert customer_client.get("/finance/refunds").status_code == 403
    assert finance_client.get("/finance/refunds").status_code == 200
    assert customer_client.get("/community").status_code == 200
