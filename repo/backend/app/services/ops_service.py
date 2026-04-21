from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import structlog

from app.extensions import db
from app.repositories.ops_repository import OpsRepository
from app.services.errors import AppError
from app.services.payment_security import PaymentSecurity
from app.services.time_utils import utc_now_naive
from flask import current_app


logger = structlog.get_logger(__name__)


class MenuCache:
    # Guard the class-level store with a reentrant lock so concurrent put/get
    # from worker threads cannot corrupt the mapping or race on the
    # lazy-expiry pop inside get().
    _lock: threading.RLock = threading.RLock()
    store: dict[str, tuple[datetime, object]] = {}

    @classmethod
    def get(cls, key: str, ttl_seconds: int):
        with cls._lock:
            item = cls.store.get(key)
            if item is None:
                return None
            created_at, value = item
            if created_at + timedelta(seconds=ttl_seconds) < utc_now_naive():
                cls.store.pop(key, None)
                return None
            return value

    @classmethod
    def put(cls, key: str, value: object):
        with cls._lock:
            cls.store[key] = (utc_now_naive(), value)

    @classmethod
    def clear(cls):
        with cls._lock:
            cls.store.clear()


class OpsService:
    # Gate maintenance work so it runs at most once per minimum interval,
    # decoupling it from the hot request path. Class-level so the gate is
    # shared across all OpsService instances within a worker process.
    _maintenance_lock: threading.RLock = threading.RLock()
    _last_maintenance_at: datetime | None = None

    def __init__(self, repository: OpsRepository) -> None:
        self.repository = repository
        self.security = PaymentSecurity(PaymentSecurity.derive_fernet_key(current_app.config["KEY_ENCRYPTION_SECRET"]))

    def enqueue_job(self, job_type: str, payload: dict, available_at: datetime | None = None):
        job = self.repository.create_job(
            job_type=job_type,
            payload_json=json.dumps(payload),
            status="queued",
            attempts=0,
            max_attempts=3,
            available_at=available_at or utc_now_naive(),
            last_error="",
        )
        db.session.commit()
        return job

    def process_next_job(self):
        started_at = utc_now_naive()
        # Atomic claim: only one worker can transition a queued row to
        # running, so duplicate execution of the same reconciliation or
        # bulk-menu job is impossible under concurrent processing.
        job = self.repository.claim_next_available_job(started_at)
        if job is None:
            return None
        run = self.repository.add_job_run(
            job_id=job.id,
            status="running",
            started_at=started_at,
            finished_at=None,
            details_json=job.payload_json,
        )
        try:
            payload = json.loads(job.payload_json or "{}")
            result = self._execute_job(job.job_type, payload)
            job.status = "completed"
            job.last_error = ""
            run.status = "completed"
            run.finished_at = utc_now_naive()
            run.details_json = json.dumps({"payload": payload, "result": result})
            logger.info("ops.job_completed", job_id=job.id, job_type=job.job_type)
        except Exception as exc:
            job.last_error = str(exc)
            job.status = "dead_letter" if job.attempts >= job.max_attempts else "queued"
            job.available_at = utc_now_naive() + timedelta(seconds=30)
            run.status = "failed"
            run.finished_at = utc_now_naive()
            run.details_json = json.dumps({"payload": job.payload_json, "error": str(exc)})
            logger.warning(
                "ops.job_failed",
                job_id=job.id,
                job_type=job.job_type,
                attempts=job.attempts,
                status=job.status,
            )
        db.session.add(job)
        db.session.add(run)
        db.session.commit()
        return job

    def process_jobs(self, limit: int = 1):
        normalized_limit = max(1, min(int(limit), 50))
        processed = []
        for _ in range(normalized_limit):
            job = self.process_next_job()
            if job is None:
                break
            processed.append(job)
        return processed

    def run_maintenance_tick(self, now: datetime | None = None, force: bool = False):
        explicit_time = now is not None
        reference_time = now or utc_now_naive()
        # When the caller passes no explicit time, this is a request-path tick
        # and must not hammer the maintenance code on every request. Coalesce
        # to at most one run per minimum-interval window using a class-level
        # lock. Explicit-time calls (tests, scheduler harness) bypass the gate
        # so callers stay in control of when work actually fires.
        if not explicit_time and not force:
            min_interval = int(current_app.config.get("OPS_MAINTENANCE_MIN_INTERVAL_SECONDS", 5))
            with OpsService._maintenance_lock:
                last = OpsService._last_maintenance_at
                if last is not None and reference_time - last < timedelta(seconds=min_interval):
                    return {"backup_job_id": None, "processed_job_ids": [], "skipped": True}
                OpsService._last_maintenance_at = reference_time
        backup_job = self._run_nightly_backup_if_due(reference_time)
        processed_jobs = self.process_jobs(current_app.config["OPS_JOB_PROCESS_LIMIT_PER_TICK"])
        return {
            "backup_job_id": backup_job.id if backup_job else None,
            "processed_job_ids": [job.id for job in processed_jobs],
        }

    def enforce_rate_limit(self, actor_key: str):
        now = utc_now_naive()
        bucket_key = f"{actor_key}:{now.strftime('%Y%m%d%H%M')}"
        # Atomic UPSERT with server-side increment. SQLite serializes writes
        # behind its exclusive write lock, so a single-statement
        # INSERT ... ON CONFLICT DO UPDATE with an additive counter cannot
        # lose concurrent increments — unlike a read-modify-write in Python.
        new_count = db.session.execute(
            db.text(
                """
                INSERT INTO rate_limit_buckets (
                    id, bucket_key, window_started_at, request_count, created_at, updated_at
                )
                VALUES (:id, :bucket_key, :window, 1, :now, :now)
                ON CONFLICT(bucket_key) DO UPDATE SET
                    request_count = request_count + 1,
                    updated_at = :now
                RETURNING request_count
                """
            ),
            {
                "id": str(uuid4()),
                "bucket_key": bucket_key,
                "window": now.replace(second=0, microsecond=0),
                "now": now,
            },
        ).scalar()
        db.session.commit()
        if new_count > current_app.config["RATE_LIMIT_PER_MINUTE"]:
            raise AppError(
                "rate_limited",
                "Rate limit exceeded.",
                429,
                {"limit": current_app.config["RATE_LIMIT_PER_MINUTE"]},
            )

    def before_endpoint(self, endpoint_key: str):
        now = utc_now_naive()
        reset_seconds = int(current_app.config["CIRCUIT_BREAKER_RESET_SECONDS"])
        # Atomic self-heal: if the breaker is open and the reset window has
        # elapsed, flip it back to closed in one UPDATE so two concurrent
        # requests can't both pass while one thinks it's still healing.
        row = db.session.execute(
            db.text(
                """
                UPDATE circuit_breaker_state
                SET state = CASE
                        WHEN state = 'open'
                         AND opened_at IS NOT NULL
                         AND opened_at <= :cutoff
                        THEN 'closed'
                        ELSE state
                    END,
                    failure_count = CASE
                        WHEN state = 'open'
                         AND opened_at IS NOT NULL
                         AND opened_at <= :cutoff
                        THEN 0
                        ELSE failure_count
                    END,
                    opened_at = CASE
                        WHEN state = 'open'
                         AND opened_at IS NOT NULL
                         AND opened_at <= :cutoff
                        THEN NULL
                        ELSE opened_at
                    END,
                    updated_at = :now
                WHERE endpoint_key = :key
                RETURNING state
                """
            ),
            {
                "key": endpoint_key,
                "cutoff": now - timedelta(seconds=reset_seconds),
                "now": now,
            },
        ).first()
        db.session.commit()
        if row is not None and row[0] == "open":
            raise AppError(
                "circuit_open",
                "Endpoint temporarily unavailable due to circuit breaker.",
                503,
            )

    def record_endpoint_result(self, endpoint_key: str, failed: bool):
        now = utc_now_naive()
        threshold = int(current_app.config["CIRCUIT_BREAKER_FAILURE_THRESHOLD"])
        if failed:
            # Atomic failure-path UPSERT: the CASE-based state/opened_at
            # mutations promote the breaker to 'open' exactly when the
            # *post-increment* failure_count crosses the threshold, so
            # two concurrent failures can never both race past the
            # threshold without one of them flipping state.
            db.session.execute(
                db.text(
                    """
                    INSERT INTO circuit_breaker_state (
                        id, endpoint_key, state, failure_count, opened_at, last_failure_at, created_at, updated_at
                    )
                    VALUES (
                        :id,
                        :key,
                        CASE WHEN 1 >= :threshold THEN 'open' ELSE 'closed' END,
                        1,
                        CASE WHEN 1 >= :threshold THEN :now ELSE NULL END,
                        :now,
                        :now,
                        :now
                    )
                    ON CONFLICT(endpoint_key) DO UPDATE SET
                        failure_count = failure_count + 1,
                        last_failure_at = :now,
                        state = CASE
                            WHEN failure_count + 1 >= :threshold THEN 'open'
                            ELSE state
                        END,
                        opened_at = CASE
                            WHEN failure_count + 1 >= :threshold AND state = 'closed'
                            THEN :now
                            ELSE opened_at
                        END,
                        updated_at = :now
                    """
                ),
                {
                    "id": str(uuid4()),
                    "key": endpoint_key,
                    "threshold": threshold,
                    "now": now,
                },
            )
        else:
            # Success resets unconditionally in one statement.
            db.session.execute(
                db.text(
                    """
                    INSERT INTO circuit_breaker_state (
                        id, endpoint_key, state, failure_count, opened_at, last_failure_at, created_at, updated_at
                    )
                    VALUES (:id, :key, 'closed', 0, NULL, NULL, :now, :now)
                    ON CONFLICT(endpoint_key) DO UPDATE SET
                        state = 'closed',
                        failure_count = 0,
                        opened_at = NULL,
                        updated_at = :now
                    """
                ),
                {
                    "id": str(uuid4()),
                    "key": endpoint_key,
                    "now": now,
                },
            )
        db.session.commit()

    def list_jobs(self):
        return self.repository.list_jobs()

    def list_rate_limits(self):
        return self.repository.list_rate_buckets()

    def list_breakers(self):
        return self.repository.list_breakers()

    def run_backup(self, trigger: str = "manual", now: datetime | None = None):
        reference_time = now or utc_now_naive()
        database_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
        db_path = Path(database_uri.removeprefix("sqlite:///"))
        backup_dir = Path(current_app.config["BACKUP_DIR"])
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_name = f"tablepay-backup-{reference_time.strftime('%Y%m%d%H%M%S')}.bin"
        backup_path = backup_dir / backup_name
        encrypted = self.security.encrypt_secret(db_path.read_bytes().decode("latin1"))
        backup_path.write_text(encrypted, encoding="utf-8")
        job = self.repository.create_backup_job(
            status="completed",
            file_path=str(backup_path),
            retention_until=reference_time + timedelta(days=current_app.config["BACKUP_RETENTION_DAYS"]),
            details_json=json.dumps({"source": str(db_path), "trigger": trigger}),
        )
        self._prune_backups(reference_time)
        db.session.commit()
        logger.info("ops.backup_completed", backup_job_id=job.id, trigger=trigger)
        return job

    def restore_test(self):
        backups = self.repository.list_backup_jobs()
        if not backups:
            raise AppError("backup_missing", "No backups available to restore.", 400)
        latest = backups[0]
        restore_dir = Path(current_app.config["RESTORE_DIR"])
        restore_dir.mkdir(parents=True, exist_ok=True)
        restore_path = restore_dir / f"restore-{utc_now_naive().strftime('%Y%m%d%H%M%S')}.db"
        decrypted = self.security.decrypt_secret(Path(latest.file_path).read_text(encoding="utf-8"))
        restore_path.write_bytes(decrypted.encode("latin1"))

        # Prove the artifact is a real rebuild, not just a decrypted blob:
        # open it with a fresh sqlite connection (no shared engine, no shared
        # session) and confirm the core schema and core seed rows are
        # queryable. This is the "new machine, no network" check.
        verification = self._verify_restored_database(restore_path)
        status = "completed" if verification["ok"] else "failed"
        run = self.repository.create_restore_run(
            status=status,
            backup_job_id=latest.id,
            restore_path=str(restore_path),
            details_json=json.dumps({
                "restored_from": latest.file_path,
                "verification": verification,
            }),
        )
        db.session.commit()
        if not verification["ok"]:
            raise AppError(
                "restore_failed",
                verification.get("reason") or "Restore verification failed.",
                500,
                verification,
            )
        logger.info(
            "ops.restore_verified",
            restore_run_id=run.id,
            table_count=verification.get("table_count"),
        )
        return run

    @staticmethod
    def _verify_restored_database(restore_path: Path) -> dict:
        import sqlite3

        try:
            header = restore_path.open("rb").read(16)
        except OSError as exc:
            return {"ok": False, "reason": f"Restored file is unreadable: {exc}"}
        if not header.startswith(b"SQLite format 3\x00"):
            return {"ok": False, "reason": "Restored file is not a valid SQLite database."}

        # A real rebuild must ship with every core table the app boots
        # against — missing any of these would leave the "new instance"
        # unable to serve the feature that table backs. The grouping below
        # mirrors the app's bounded contexts (auth/catalog/payments/refunds/
        # reconciliation/moderation/ops) so a missing table flags the
        # failing domain in the error message.
        required_tables = {
            "users",
            "roles",
            "dishes",
            "dish_categories",
            "payment_transactions",
            "gateway_signing_keys",
            "refunds",
            "reconciliation_runs",
            "reconciliation_exceptions",
            "moderation_queue",
            "moderation_reason_codes",
            "job_queue",
            "backup_jobs",
            "restore_runs",
        }
        # Representative counts to sample — each probes a seeded domain so
        # the verification catches a backup that contains only schema but
        # no reference data.
        representative_counts = {
            "users": "SELECT COUNT(*) FROM users",
            "dishes": "SELECT COUNT(*) FROM dishes",
            "roles": "SELECT COUNT(*) FROM roles",
            "moderation_reason_codes": "SELECT COUNT(*) FROM moderation_reason_codes",
            "gateway_signing_keys": "SELECT COUNT(*) FROM gateway_signing_keys",
        }

        connection = sqlite3.connect(str(restore_path))
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            tables = {row[0] for row in cursor.fetchall()}
            missing = required_tables - tables
            if missing:
                return {
                    "ok": False,
                    "reason": f"Restored database is missing required tables: {sorted(missing)}",
                    "tables": sorted(tables),
                }
            counts: dict[str, int] = {}
            for name, query in representative_counts.items():
                cursor.execute(query)
                counts[name] = cursor.fetchone()[0]
        finally:
            connection.close()
        # Core reference tables must actually contain rows — an empty
        # users / roles / reason_codes table means the backup captured an
        # uninitialized app, not a working instance.
        empty = [name for name in ("users", "roles", "moderation_reason_codes") if counts.get(name, 0) == 0]
        if empty:
            return {
                "ok": False,
                "reason": f"Restored database has empty required reference tables: {empty}",
                "counts": counts,
            }
        return {
            "ok": True,
            "table_count": len(tables),
            "user_count": counts.get("users", 0),
            "dish_count": counts.get("dishes", 0),
            "counts": counts,
        }

    def _prune_backups(self, now: datetime | None = None):
        reference_time = now or utc_now_naive()
        for backup in self.repository.list_backup_jobs():
            if backup.retention_until < reference_time:
                path = Path(backup.file_path)
                if path.exists():
                    path.unlink()

    def _run_nightly_backup_if_due(self, now: datetime):
        if not current_app.config.get("NIGHTLY_BACKUP_ENABLED", False):
            return None
        database_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
        if database_uri.endswith(":memory:"):
            return None
        if now.hour < int(current_app.config["NIGHTLY_BACKUP_HOUR_UTC"]):
            return None
        latest = self.repository.latest_backup_job()
        if latest is not None and latest.created_at.date() == now.date():
            return None
        return self.run_backup(trigger="nightly_scheduler", now=now)

    def _execute_job(self, job_type: str, payload: dict):
        normalized_type = (job_type or "").strip().lower()
        if normalized_type == "reconciliation_import":
            from app.repositories.reconciliation_repository import ReconciliationRepository
            from app.services.reconciliation_service import ReconciliationService

            csv_text = payload.get("csv_text") or ""
            operator_user_id = (payload.get("operator_user_id") or "").strip()
            if not csv_text or not operator_user_id:
                raise AppError("validation_error", "Reconciliation job payload is incomplete.", 400)
            run = ReconciliationService(ReconciliationRepository()).import_csv(
                csv_text=csv_text,
                source_name=(payload.get("source_name") or "terminal_csv").strip(),
                imported_filename=(payload.get("imported_filename") or "").strip(),
                operator_user_id=operator_user_id,
                current_roles=["Finance Admin"],
            )
            return {"run_id": run.id, "status": run.status, "exception_count": run.exception_count}

        if normalized_type in {"bulk_menu_publish", "bulk_menu_update"}:
            from app.repositories.catalog_repository import CatalogRepository
            from app.services.catalog_service import CatalogService

            result = CatalogService(CatalogRepository()).apply_bulk_update(
                dish_ids=payload.get("dish_ids") or [],
                publish=payload.get("publish"),
                archived=payload.get("archived"),
            )
            return result

        raise AppError("job_unsupported", "Unsupported job type.", 400)
