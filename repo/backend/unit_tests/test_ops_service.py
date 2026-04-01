from datetime import timedelta
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


def test_backup_restore_and_retention(app, tmp_path: Path):
    with app.app_context():
        app.config["BACKUP_DIR"] = tmp_path / "backups"
        app.config["RESTORE_DIR"] = tmp_path / "restore"
        db_path = tmp_path / "db.sqlite"
        db_path.write_text("tablepay-backup-test", encoding="latin1")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path.as_posix()}"
        service = OpsService(OpsRepository())
        backup = service.run_backup()
        assert Path(backup.file_path).exists()
        assert "tablepay-backup-test" not in Path(backup.file_path).read_text(encoding="utf-8")

        restore = service.restore_test()
        assert Path(restore.restore_path).exists()
        assert Path(restore.restore_path).read_text(encoding="latin1") == "tablepay-backup-test"


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
