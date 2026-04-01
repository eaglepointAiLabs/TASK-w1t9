from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class JobQueue(BaseModel):
    __tablename__ = "job_queue"

    job_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    last_error: Mapped[str] = mapped_column(Text, nullable=False, default="")


class JobRun(BaseModel):
    __tablename__ = "job_runs"

    job_id: Mapped[str] = mapped_column(ForeignKey("job_queue.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class BackupJob(BaseModel):
    __tablename__ = "backup_jobs"

    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    retention_until: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class RestoreRun(BaseModel):
    __tablename__ = "restore_runs"

    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    backup_job_id: Mapped[str | None] = mapped_column(ForeignKey("backup_jobs.id"), nullable=True, index=True)
    restore_path: Mapped[str] = mapped_column(String(255), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class RateLimitBucket(BaseModel):
    __tablename__ = "rate_limit_buckets"
    __table_args__ = (UniqueConstraint("bucket_key", name="uq_rate_limit_bucket_key"),)

    bucket_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CircuitBreakerState(BaseModel):
    __tablename__ = "circuit_breaker_state"
    __table_args__ = (UniqueConstraint("endpoint_key", name="uq_circuit_breaker_endpoint"),)

    endpoint_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="closed", index=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


__all__ = [
    "BackupJob",
    "CircuitBreakerState",
    "JobQueue",
    "JobRun",
    "RateLimitBucket",
    "RestoreRun",
]
