from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.extensions import db
from app.models import BackupJob, CircuitBreakerState, JobQueue, JobRun, RateLimitBucket, RestoreRun


class OpsRepository:
    def create_job(self, **kwargs) -> JobQueue:
        job = JobQueue(**kwargs)
        db.session.add(job)
        db.session.flush()
        return job

    def add_job_run(self, **kwargs) -> JobRun:
        run = JobRun(**kwargs)
        db.session.add(run)
        db.session.flush()
        return run

    def list_jobs(self) -> list[JobQueue]:
        stmt = select(JobQueue).order_by(JobQueue.created_at.desc())
        return list(db.session.scalars(stmt))

    def next_available_job(self, now: datetime) -> JobQueue | None:
        stmt = select(JobQueue).where(JobQueue.status == "queued", JobQueue.available_at <= now).order_by(JobQueue.created_at.asc())
        return db.session.scalar(stmt)

    def claim_next_available_job(self, now: datetime) -> JobQueue | None:
        """
        Atomically claim the oldest queued job whose availability has arrived.

        The UPDATE ... WHERE id = (SELECT ... LIMIT 1) RETURNING pattern is a
        single SQL statement. SQLite serializes writes behind its exclusive
        write lock, so two workers issuing this concurrently cannot both see
        the row as 'queued' — the second worker's subquery evaluates after
        the first worker's UPDATE commits, and the row's new state is
        'running' so it is no longer a candidate.
        """
        claimed_id = db.session.execute(
            db.text(
                """
                UPDATE job_queue
                SET status = 'running',
                    attempts = attempts + 1,
                    updated_at = :now
                WHERE id = (
                    SELECT id FROM job_queue
                    WHERE status = 'queued'
                      AND available_at <= :now
                    ORDER BY created_at ASC
                    LIMIT 1
                )
                RETURNING id
                """
            ),
            {"now": now},
        ).scalar()
        db.session.commit()
        if claimed_id is None:
            return None
        return db.session.scalar(select(JobQueue).where(JobQueue.id == claimed_id))

    def get_rate_bucket(self, bucket_key: str) -> RateLimitBucket | None:
        stmt = select(RateLimitBucket).where(RateLimitBucket.bucket_key == bucket_key)
        return db.session.scalar(stmt)

    def create_rate_bucket(self, **kwargs) -> RateLimitBucket:
        bucket = RateLimitBucket(**kwargs)
        db.session.add(bucket)
        db.session.flush()
        return bucket

    def list_rate_buckets(self) -> list[RateLimitBucket]:
        stmt = select(RateLimitBucket).order_by(RateLimitBucket.updated_at.desc())
        return list(db.session.scalars(stmt))

    def get_breaker(self, endpoint_key: str) -> CircuitBreakerState | None:
        stmt = select(CircuitBreakerState).where(CircuitBreakerState.endpoint_key == endpoint_key)
        return db.session.scalar(stmt)

    def create_breaker(self, **kwargs) -> CircuitBreakerState:
        breaker = CircuitBreakerState(**kwargs)
        db.session.add(breaker)
        db.session.flush()
        return breaker

    def list_breakers(self) -> list[CircuitBreakerState]:
        stmt = select(CircuitBreakerState).order_by(CircuitBreakerState.endpoint_key.asc())
        return list(db.session.scalars(stmt))

    def create_backup_job(self, **kwargs) -> BackupJob:
        job = BackupJob(**kwargs)
        db.session.add(job)
        db.session.flush()
        return job

    def list_backup_jobs(self) -> list[BackupJob]:
        stmt = select(BackupJob).order_by(BackupJob.created_at.desc())
        return list(db.session.scalars(stmt))

    def latest_backup_job(self) -> BackupJob | None:
        stmt = select(BackupJob).order_by(BackupJob.created_at.desc())
        return db.session.scalar(stmt)

    def create_restore_run(self, **kwargs) -> RestoreRun:
        run = RestoreRun(**kwargs)
        db.session.add(run)
        db.session.flush()
        return run
