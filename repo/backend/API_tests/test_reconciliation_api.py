from app.extensions import db


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


def test_reconciliation_mutations_require_authenticated_session(client):
    csrf_token = fetch_csrf(client)

    import_response = client.post(
        "/api/finance/reconciliation/import",
        json={
            "source_name": "terminal_csv",
            "statement_csv": "transaction_reference,amount,currency,status\nunauth-1,10.25,USD,success\n",
            "filename": "terminal.csv",
        },
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert import_response.status_code == 401
    assert import_response.json["code"] == "authentication_required"

    resolve_response = client.post(
        "/api/finance/reconciliation/exceptions/nonexistent-id/resolve",
        json={"action_type": "resolve", "reason": "no session"},
        headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"},
    )
    assert resolve_response.status_code == 401
    assert resolve_response.json["code"] == "authentication_required"


def test_reconciliation_import_and_list_runs(client, app):
    finance_csrf = login(client, "finance", "Finance#12345")
    with app.app_context():
        order_id = db.session.execute(db.text("select id from orders limit 1")).scalar()
    client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-recon-1",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )

    import_response = client.post(
        "/api/finance/reconciliation/import",
        json={
            "source_name": "terminal_csv",
            "statement_csv": "transaction_reference,amount,currency,status\napi-recon-1,10.25,USD,success\n",
            "filename": "terminal.csv",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert import_response.status_code == 201
    run_id = import_response.json["data"]["id"]

    list_response = client.get("/api/finance/reconciliation/runs", headers={"Accept": "application/json"})
    assert list_response.status_code == 200
    assert any(run["id"] == run_id for run in list_response.json["data"])


def test_reconciliation_async_import_uses_job_queue(client, app):
    finance_csrf = login(client, "finance", "Finance#12345")
    with app.app_context():
        order_id = db.session.execute(db.text("select id from orders limit 1")).scalar()
    client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-recon-async-1",
            "capture_amount": "10.25",
            "status": "success",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )

    enqueue_response = client.post(
        "/api/finance/reconciliation/import/async",
        json={
            "source_name": "terminal_csv",
            "statement_csv": "transaction_reference,amount,currency,status\napi-recon-async-1,10.25,USD,success\n",
            "filename": "async-terminal.csv",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert enqueue_response.status_code == 202
    job_id = enqueue_response.json["data"]["job_id"]

    process_response = client.post(
        "/api/admin/ops/jobs/process",
        json={"count": 1},
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert process_response.status_code == 200
    assert process_response.json["data"][0]["id"] == job_id
    assert process_response.json["data"][0]["status"] == "completed"

    list_response = client.get("/api/finance/reconciliation/runs", headers={"Accept": "application/json"})
    assert list_response.status_code == 200
    assert any(run["source_name"] == "terminal_csv" and run["exception_count"] == 0 for run in list_response.json["data"])


def test_reconciliation_resolution_flow(client, app):
    finance_csrf = login(client, "finance", "Finance#12345")
    with app.app_context():
        order_id = db.session.execute(db.text("select id from orders limit 1")).scalar()
    client.post(
        "/api/payments/capture",
        json={
            "order_id": order_id,
            "transaction_reference": "api-recon-2",
            "capture_amount": "10.25",
            "status": "pending",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )

    import_response = client.post(
        "/api/finance/reconciliation/import",
        json={
            "source_name": "terminal_csv",
            "statement_csv": "transaction_reference,amount,currency,status\napi-recon-2,10.25,USD,success\n",
            "filename": "terminal.csv",
        },
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    exception_id = import_response.json["data"]["exceptions"][0]["id"]
    run_id = import_response.json["data"]["id"]

    resolve_response = client.post(
        f"/api/finance/reconciliation/exceptions/{exception_id}/resolve",
        json={"action_type": "resolve", "reason": "Accepted mismatch after manual review."},
        headers={"X-CSRF-Token": finance_csrf, "Accept": "application/json"},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json["data"]["status"] == "resolved"

    run_response = client.get(
        f"/api/finance/reconciliation/runs/{run_id}",
        headers={"Accept": "application/json"},
    )
    assert run_response.status_code == 200
    assert run_response.json["data"]["exceptions"][0]["status"] == "resolved"
