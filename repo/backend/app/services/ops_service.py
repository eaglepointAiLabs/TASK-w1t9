from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import structlog

from app.extensions import db
from app.repositories.ops_repository import OpsRepository
from app.services.errors import AppError
from app.services.payment_security import PaymentSecurity
from app.services.time_utils import utc_now_naive
from flask import current_app


logger = structlog.get_logger(__name__)


class MenuCache:
    store: dict[str, tuple[datetime, object]] = {}

    @classmethod
    def get(cls, key: str, ttl_seconds: int):
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
        cls.store[key] = (utc_now_naive(), value)

    @classmethod
    def clear(cls):
        cls.store.clear()


class OpsService:
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
        job = self.repository.next_available_job(started_at)
        if job is None:
            return None
        job.status = "running"
        job.attempts += 1
        db.session.add(job)
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

    def run_maintenance_tick(self, now: datetime | None = None):
        reference_time = now or utc_now_naive()
        backup_job = self._run_nightly_backup_if_due(reference_time)
        processed_jobs = self.process_jobs(current_app.config["OPS_JOB_PROCESS_LIMIT_PER_TICK"])
        return {
            "backup_job_id": backup_job.id if backup_job else None,
            "processed_job_ids": [job.id for job in processed_jobs],
        }

    def enforce_rate_limit(self, actor_key: str):
        now = utc_now_naive()
        bucket_key = f"{actor_key}:{now.strftime('%Y%m%d%H%M')}"
        bucket = self.repository.get_rate_bucket(bucket_key)
        if bucket is None:
            bucket = self.repository.create_rate_bucket(
                bucket_key=bucket_key,
                window_started_at=now.replace(second=0, microsecond=0),
                request_count=0,
            )
        bucket.request_count += 1
        db.session.add(bucket)
        db.session.commit()
        if bucket.request_count > current_app.config["RATE_LIMIT_PER_MINUTE"]:
            raise AppError("rate_limited", "Rate limit exceeded.", 429, {"limit": current_app.config["RATE_LIMIT_PER_MINUTE"]})

    def before_endpoint(self, endpoint_key: str):
        breaker = self.repository.get_breaker(endpoint_key)
        if breaker and breaker.state == "open" and breaker.opened_at and breaker.opened_at + timedelta(seconds=current_app.config["CIRCUIT_BREAKER_RESET_SECONDS"]) > utc_now_naive():
            raise AppError("circuit_open", "Endpoint temporarily unavailable due to circuit breaker.", 503)
        if breaker and breaker.state == "open":
            breaker.state = "closed"
            breaker.failure_count = 0
            breaker.opened_at = None
            db.session.add(breaker)
            db.session.commit()

    def record_endpoint_result(self, endpoint_key: str, failed: bool):
        breaker = self.repository.get_breaker(endpoint_key)
        if breaker is None:
            breaker = self.repository.create_breaker(
                endpoint_key=endpoint_key,
                state="closed",
                failure_count=0,
                opened_at=None,
                last_failure_at=None,
            )
        if failed:
            breaker.failure_count += 1
            breaker.last_failure_at = utc_now_naive()
            if breaker.failure_count >= current_app.config["CIRCUIT_BREAKER_FAILURE_THRESHOLD"]:
                breaker.state = "open"
                breaker.opened_at = utc_now_naive()
        else:
            breaker.failure_count = 0
            breaker.state = "closed"
            breaker.opened_at = None
        db.session.add(breaker)
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
        run = self.repository.create_restore_run(
            status="completed",
            backup_job_id=latest.id,
            restore_path=str(restore_path),
            details_json=json.dumps({"restored_from": latest.file_path}),
        )
        db.session.commit()
        return run

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
