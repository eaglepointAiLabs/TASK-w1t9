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


def test_ops_endpoints_and_backup_restore(client, app, tmp_path):
    csrf_token = login(client, "finance", "Finance#12345")
    with app.app_context():
        app.config["BACKUP_DIR"] = tmp_path / "backups"
        app.config["RESTORE_DIR"] = tmp_path / "restore"
        db_path = tmp_path / "ops-db.sqlite"
        db_path.write_text("ops-backup-test", encoding="latin1")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path.as_posix()}"

    jobs = client.get("/api/admin/ops/jobs", headers={"Accept": "application/json"})
    assert jobs.status_code == 200

    backup = client.post("/api/admin/ops/backups/run", headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"})
    assert backup.status_code == 200

    restore = client.post("/api/admin/ops/restore/test", headers={"X-CSRF-Token": csrf_token, "Accept": "application/json"})
    assert restore.status_code == 200

    breakers = client.get("/api/admin/ops/circuit-breakers", headers={"Accept": "application/json"})
    assert breakers.status_code == 200

    rate_limits = client.get("/api/admin/ops/rate-limits", headers={"Accept": "application/json"})
    assert rate_limits.status_code == 200
from pathlib import Path
