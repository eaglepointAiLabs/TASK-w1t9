from datetime import timedelta
import json
from pathlib import Path

from app.extensions import db
from app.repositories.auth_repository import AuthRepository
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.ops_repository import OpsRepository
from app.repositories.payment_repository import PaymentRepository
from app.services.ops_service import MenuCache, OpsService
from app.services.payment_service import PaymentService
from app.services.time_utils import utc_now_naive


def _finance_user_id() -> str:
    return AuthRepository().get_user_by_username("finance").id


def test_menu_cache_behavior_and_expiry():
    MenuCache.clear()
    MenuCache.put("menu-key", ["a"])
    assert MenuCache.get("menu-key", 60) == ["a"]
    MenuCache.store["expired-key"] = (utc_now_naive() - timedelta(seconds=61), ["b"])
    assert MenuCache.get("expired-key", 60) is None


def test_rate_limit_and_circuit_breaker(app):
    with app.app_context():
        service = OpsService(OpsRepository())
        limited = False
        for _ in range(61):
            try:
                service.enforce_rate_limit("user-1")
            except Exception as exc:
                limited = getattr(exc, "code", "") == "rate_limited"
                break
        assert limited

        for _ in range(5):
            service.record_endpoint_result("/api/test", True)
        open_hit = False
        try:
            service.before_endpoint("/api/test")
        except Exception as exc:
            open_hit = getattr(exc, "code", "") == "circuit_open"
        assert open_hit


def test_rate_limit_counter_is_atomic_across_many_increments(app):
    """
    The rate-limit bucket counter must increment by exactly one per call —
    the UPSERT-with-RETURNING implementation relies on a single SQL statement
    rather than a Python read-modify-write, so no increments can be lost
    under serialized writes.
    """
    with app.app_context():
        app.config["RATE_LIMIT_PER_MINUTE"] = 10_000
        service = OpsService(OpsRepository())
        for _ in range(50):
            service.enforce_rate_limit("user-atomic")
        count = db.session.execute(
            db.text(
                "SELECT request_count FROM rate_limit_buckets WHERE bucket_key LIKE 'user-atomic:%'"
            )
        ).scalar()
        assert count == 50


def test_circuit_breaker_opens_atomically_at_threshold(app):
    """
    The breaker must flip from 'closed' to 'open' in the same SQL statement
    that lands the Nth failure — a post-commit check-then-set would let two
    concurrent failures both cross the threshold without either promoting
    the state.
    """
    with app.app_context():
        service = OpsService(OpsRepository())
        threshold = int(app.config["CIRCUIT_BREAKER_FAILURE_THRESHOLD"])
        for _ in range(threshold - 1):
            service.record_endpoint_result("/api/atomic-breaker", True)
        state_before = db.session.execute(
            db.text(
                "SELECT state, failure_count FROM circuit_breaker_state WHERE endpoint_key = '/api/atomic-breaker'"
            )
        ).first()
        assert state_before.state == "closed"
        assert state_before.failure_count == threshold - 1

        service.record_endpoint_result("/api/atomic-breaker", True)
        state_after = db.session.execute(
            db.text(
                "SELECT state, failure_count, opened_at FROM circuit_breaker_state WHERE endpoint_key = '/api/atomic-breaker'"
            )
        ).first()
        assert state_after.state == "open"
        assert state_after.failure_count == threshold
        assert state_after.opened_at is not None


def test_maintenance_tick_is_decoupled_from_request_path(app):
    """
    run_maintenance_tick() called without an explicit 'now' (the request-path
    mode) must coalesce closely-spaced calls so maintenance work does not
    fire on every incoming request.
    """
    with app.app_context():
        app.config["OPS_MAINTENANCE_MIN_INTERVAL_SECONDS"] = 30
        OpsService._last_maintenance_at = None
        service = OpsService(OpsRepository())

        first = service.run_maintenance_tick()
        second = service.run_maintenance_tick()
        third = service.run_maintenance_tick()

        assert first.get("skipped") is not True
        assert second.get("skipped") is True
        assert third.get("skipped") is True

        # An explicit time (test harness / scheduler) bypasses the gate.
        forced = service.run_maintenance_tick(now=utc_now_naive() + timedelta(hours=1))
        assert forced.get("skipped") is not True


def test_backup_restore_and_retention(file_app, tmp_path: Path):
    # file_app is a file-backed sqlite database with the full seeded schema,
    # so the restore-time verification (which probes users / dishes / roles /
    # payment / moderation tables) has a realistic artifact to validate.
    with file_app.app_context():
        file_app.config["BACKUP_DIR"] = tmp_path / "backups"
        file_app.config["RESTORE_DIR"] = tmp_path / "restore"
        service = OpsService(OpsRepository())
        backup = service.run_backup()
        assert Path(backup.file_path).exists()
        # Backup artifact must be encrypted — the SQLite magic header must
        # never leak through to disk.
        assert b"SQLite format 3" not in Path(backup.file_path).read_bytes()

        restore = service.restore_test()
        assert Path(restore.restore_path).exists()
        assert restore.status == "completed"


def test_restore_produces_functioning_fresh_instance(file_app, tmp_path: Path):
    """
    The restore path must produce an artifact that could be used as a fresh
    instance on a new machine with no network access — i.e., a standalone
    sqlite database that a brand-new connection can open and query.
    """
    import sqlite3

    with file_app.app_context():
        file_app.config["BACKUP_DIR"] = tmp_path / "backups"
        file_app.config["RESTORE_DIR"] = tmp_path / "restore"
        live_db_path = Path(file_app.config["SQLALCHEMY_DATABASE_URI"].removeprefix("sqlite:///"))

        service = OpsService(OpsRepository())
        service.run_backup()

        restore = service.restore_test()
        assert restore.status == "completed"
        details = json.loads(restore.details_json)
        assert details["verification"]["ok"] is True
        assert details["verification"]["user_count"] > 0
        assert details["verification"]["dish_count"] > 0
        # Full-schema verification must cover every bounded-context table,
        # not just users and dishes.
        assert details["verification"]["counts"]["roles"] > 0
        assert details["verification"]["counts"]["moderation_reason_codes"] > 0
        assert details["verification"]["counts"]["gateway_signing_keys"] > 0

        # Open the restored file with a brand-new sqlite connection — no
        # shared engine, no shared session, no app context. If this works,
        # the artifact is a functioning fresh instance.
        with sqlite3.connect(str(Path(restore.restore_path))) as fresh:
            user_count = fresh.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            dish_count = fresh.execute("SELECT COUNT(*) FROM dishes").fetchone()[0]
            payment_table = fresh.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'payment_transactions'"
            ).fetchone()
            refund_table = fresh.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'refunds'"
            ).fetchone()
            reconciliation_table = fresh.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'reconciliation_runs'"
            ).fetchone()
            moderation_table = fresh.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'moderation_queue'"
            ).fetchone()
            ops_table = fresh.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'job_queue'"
            ).fetchone()
        assert user_count > 0
        assert dish_count > 0
        assert payment_table is not None, "payment_transactions table missing from restored artifact"
        assert refund_table is not None, "refunds table missing from restored artifact"
        assert reconciliation_table is not None, "reconciliation_runs table missing from restored artifact"
        assert moderation_table is not None, "moderation_queue table missing from restored artifact"
        assert ops_table is not None, "job_queue table missing from restored artifact"

        # Live DB path is still intact on disk (we didn't unlink it), so the
        # session cleanup in the fixture can drop it cleanly.
        assert live_db_path.exists()


def test_restore_rejects_invalid_backup_artifact(app, tmp_path: Path):
    """
    A backup that does not decrypt to a valid SQLite file must NOT be
    marked as a successful restore — the RestoreRun status must be 'failed'
    and the caller must see an error.
    """
    with app.app_context():
        app.config["BACKUP_DIR"] = tmp_path / "backups"
        app.config["RESTORE_DIR"] = tmp_path / "restore"
        db_path = tmp_path / "not-a-sqlite.bin"
        db_path.write_bytes(b"this is plainly not a sqlite database")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path.as_posix()}"

        service = OpsService(OpsRepository())
        service.run_backup()

        failed = False
        try:
            service.restore_test()
        except Exception as exc:
            failed = getattr(exc, "code", "") == "restore_failed"
        assert failed, "Restore must raise when the artifact is not a valid SQLite database"

        # The RestoreRun for the failed attempt must be recorded as 'failed'.
        rows = db.session.execute(
            db.text("SELECT status FROM restore_runs ORDER BY created_at DESC LIMIT 1")
        ).fetchall()
        assert rows and rows[0][0] == "failed"


def test_job_claim_is_atomic_no_duplicate_execution(app):
    """
    Two workers calling claim_next_available_job concurrently (simulated by
    back-to-back calls in the same session) must never both claim the same
    queued job. The first call transitions the row to 'running' in one
    statement; the second call sees no 'queued' row with that id.
    """
    with app.app_context():
        service = OpsService(OpsRepository())
        repo = OpsRepository()
        # Enqueue one job.
        from app.repositories.catalog_repository import CatalogRepository

        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")
        job = service.enqueue_job(
            "bulk_menu_update",
            {
                "dish_ids": [dish.id],
                "publish": True,
                "archived": False,
                "operator_user_id": _finance_user_id(),
            },
        )

        first = repo.claim_next_available_job(utc_now_naive())
        second = repo.claim_next_available_job(utc_now_naive())

        assert first is not None
        assert first.id == job.id
        assert first.status == "running"
        assert first.attempts == 1
        assert second is None, "A second worker must not re-claim the same job"


def test_process_jobs_does_not_duplicate_execution_under_contention(app):
    """
    Even when process_jobs is invoked multiple times across workers, each
    queued job is executed exactly once. We stage two queued jobs, then
    simulate two workers each trying to process two jobs; exactly two job
    runs end in 'completed' — no duplicates.
    """
    with app.app_context():
        from app.repositories.catalog_repository import CatalogRepository

        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")
        service = OpsService(OpsRepository())
        job1 = service.enqueue_job(
            "bulk_menu_update",
            {
                "dish_ids": [dish.id],
                "publish": True,
                "archived": False,
                "operator_user_id": _finance_user_id(),
            },
        )
        job2 = service.enqueue_job(
            "bulk_menu_update",
            {
                "dish_ids": [dish.id],
                "publish": False,
                "archived": False,
                "operator_user_id": _finance_user_id(),
            },
        )

        # Worker A claims and processes up to 5; Worker B, interleaved, also
        # asks for 5. Total completed runs across both must be exactly 2.
        processed_a = service.process_jobs(limit=5)
        processed_b = service.process_jobs(limit=5)

        completed_ids = {p.id for p in processed_a + processed_b if p.status == "completed"}
        assert completed_ids == {job1.id, job2.id}

        # Every JobRun attached to job1 / job2 with status='completed' must
        # occur exactly once — no duplicate runs.
        completed_runs = db.session.execute(
            db.text(
                "SELECT job_id, COUNT(*) AS c FROM job_runs "
                "WHERE status = 'completed' GROUP BY job_id"
            )
        ).fetchall()
        counts = {row.job_id: row.c for row in completed_runs}
        assert counts.get(job1.id) == 1
        assert counts.get(job2.id) == 1


def test_async_reconciliation_job_executes_business_logic(app):
    with app.app_context():
        order_id = db.session.execute(db.text("select id from orders limit 1")).scalar()
        PaymentService(PaymentRepository()).capture_payment(
            {
                "order_id": order_id,
                "transaction_reference": "ops-async-recon-1",
                "capture_amount": "10.25",
                "status": "success",
            },
            ["Finance Admin"],
        )

        service = OpsService(OpsRepository())
        job = service.enqueue_job(
            "reconciliation_import",
            {
                "csv_text": "transaction_reference,amount,currency,status\nops-async-recon-1,10.25,USD,success\n",
                "source_name": "terminal_csv",
                "imported_filename": "ops-async-recon.csv",
                "operator_user_id": _finance_user_id(),
            },
        )

        processed = service.process_next_job()

        assert processed is not None
        assert processed.id == job.id
        assert processed.status == "completed"
        run_row = db.session.execute(
            db.text(
                "select total_rows, matched_rows, exception_count "
                "from reconciliation_runs where imported_filename = 'ops-async-recon.csv'"
            )
        ).first()
        assert run_row is not None
        assert run_row.total_rows == 1
        assert run_row.matched_rows == 1
        assert run_row.exception_count == 0


def test_async_bulk_menu_job_updates_dish_state(app):
    with app.app_context():
        repository = CatalogRepository()
        dish = repository.get_dish_by_slug("citrus-tofu-bowl")
        dish.is_published = False
        dish.archived_at = utc_now_naive()
        db.session.add(dish)
        db.session.commit()

        service = OpsService(OpsRepository())
        job = service.enqueue_job(
            "bulk_menu_update",
            {
                "dish_ids": [dish.id],
                "publish": True,
                "archived": False,
                "operator_user_id": _finance_user_id(),
            },
        )

        processed = service.process_next_job()

        assert processed is not None
        assert processed.id == job.id
        assert processed.status == "completed"
        refreshed = repository.get_dish(dish.id)
        assert refreshed.is_published is True
        assert refreshed.archived_at is None


def test_maintenance_tick_runs_nightly_backup_and_processes_jobs(app, tmp_path: Path):
    with app.app_context():
        app.config["NIGHTLY_BACKUP_ENABLED"] = True
        app.config["NIGHTLY_BACKUP_HOUR_UTC"] = 0
        app.config["OPS_JOB_PROCESS_LIMIT_PER_TICK"] = 1
        app.config["BACKUP_DIR"] = tmp_path / "backups"
        db_path = tmp_path / "scheduled-db.sqlite"
        db_path.write_text("scheduled-backup", encoding="latin1")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path.as_posix()}"

        repository = CatalogRepository()
        dish = repository.get_dish_by_slug("citrus-tofu-bowl")
        dish.is_published = False
        db.session.add(dish)
        db.session.commit()

        service = OpsService(OpsRepository())
        service.enqueue_job(
            "bulk_menu_update",
            {
                "dish_ids": [dish.id],
                "publish": True,
                "archived": False,
                "operator_user_id": _finance_user_id(),
            },
        )

        now = utc_now_naive().replace(hour=23, minute=0, second=0, microsecond=0)
        first_tick = service.run_maintenance_tick(now=now)
        second_tick = service.run_maintenance_tick(now=now + timedelta(minutes=1))

        assert first_tick["backup_job_id"] is not None
        assert len(first_tick["processed_job_ids"]) == 1
        assert second_tick["backup_job_id"] is None
        backup_files = list((tmp_path / "backups").glob("tablepay-backup-*.bin"))
        assert backup_files
