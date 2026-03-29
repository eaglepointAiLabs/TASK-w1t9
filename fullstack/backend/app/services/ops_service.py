from __future__ import annotations

import json
import shutil
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

    def enqueue_job(self, job_type: str, payload: dict):
        job = self.repository.create_job(
            job_type=job_type,
            payload_json=json.dumps(payload),
            status="queued",
            attempts=0,
            max_attempts=3,
            available_at=utc_now_naive(),
            last_error="",
        )
        db.session.commit()
        return job

    def process_next_job(self):
        job = self.repository.next_available_job(utc_now_naive())
        if job is None:
            return None
        job.status = "running"
        job.attempts += 1
        db.session.add(job)
        run = self.repository.add_job_run(
            job_id=job.id,
            status="running",
            started_at=utc_now_naive(),
            finished_at=None,
            details_json=job.payload_json,
        )
        try:
            payload = json.loads(job.payload_json)
            if job.job_type not in {"reconciliation_import", "bulk_menu_publish"}:
                raise AppError("job_unsupported", "Unsupported job type.", 400)
            job.status = "completed"
            run.status = "completed"
            run.finished_at = utc_now_naive()
        except Exception as exc:
            job.last_error = str(exc)
            job.status = "dead_letter" if job.attempts >= job.max_attempts else "queued"
            job.available_at = utc_now_naive() + timedelta(seconds=30)
            run.status = "failed"
            run.finished_at = utc_now_naive()
        db.session.add(job)
        db.session.add(run)
        db.session.commit()
        return job

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

    def run_backup(self):
        database_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
        db_path = Path(database_uri.removeprefix("sqlite:///"))
        backup_dir = Path(current_app.config["BACKUP_DIR"])
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_name = f"tablepay-backup-{utc_now_naive().strftime('%Y%m%d%H%M%S')}.bin"
        backup_path = backup_dir / backup_name
        encrypted = self.security.encrypt_secret(db_path.read_bytes().decode("latin1"))
        backup_path.write_text(encrypted, encoding="utf-8")
        job = self.repository.create_backup_job(
            status="completed",
            file_path=str(backup_path),
            retention_until=utc_now_naive() + timedelta(days=current_app.config["BACKUP_RETENTION_DAYS"]),
            details_json=json.dumps({"source": str(db_path)}),
        )
        self._prune_backups()
        db.session.commit()
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

    def _prune_backups(self):
        for backup in self.repository.list_backup_jobs():
            if backup.retention_until < utc_now_naive():
                path = Path(backup.file_path)
                if path.exists():
                    path.unlink()
