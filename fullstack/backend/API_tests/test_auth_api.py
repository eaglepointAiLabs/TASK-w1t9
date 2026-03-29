def fetch_csrf(client):
    response = client.get("/login")
    html = response.get_data(as_text=True)
    marker = 'name="csrf_token" value="'
    token = html.split(marker)[1].split('"')[0]
    return token


def test_login_success_and_me(client):
    csrf_token = fetch_csrf(client)
    login_response = client.post(
        "/auth/login",
        json={"username": "customer", "password": "Customer#1234"},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )

    assert login_response.status_code == 200
    assert login_response.json["data"]["username"] == "customer"
    assert login_response.headers["X-CSRF-Token"]

    me_response = client.get("/auth/me", headers={"Accept": "application/json"})
    assert me_response.status_code == 200
    assert me_response.json["data"]["authenticated"] is True
    assert me_response.json["data"]["roles"] == ["Customer"]


def test_login_rejects_missing_csrf(client):
    response = client.post(
        "/auth/login",
        json={"username": "customer", "password": "Customer#1234"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 403
    assert response.json["code"] == "csrf_required"


def test_login_lockout_after_repeated_failures(client):
    csrf_token = fetch_csrf(client)
    for _ in range(10):
        response = client.post(
            "/auth/login",
            json={"username": "customer", "password": "bad-password"},
            headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
        )
        assert response.status_code == 401

    locked_response = client.post(
        "/auth/login",
        json={"username": "customer", "password": "bad-password"},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert locked_response.status_code == 423
    assert locked_response.json["code"] == "account_locked"


def test_logout_requires_csrf(client):
    response = client.post("/auth/logout", headers={"Accept": "application/json"})

    assert response.status_code == 403


def test_home_requires_session(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
