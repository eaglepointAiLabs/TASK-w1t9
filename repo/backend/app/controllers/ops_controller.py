from __future__ import annotations

from flask import g, jsonify, request

from app.repositories.ops_repository import OpsRepository
from app.services.errors import AppError
from app.services.ops_service import OpsService
from app.services.rbac_service import RBACService
from app.services.time_utils import serialize_utc_datetime


def _service():
    return OpsService(OpsRepository())


def _require_admin():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    RBACService().require_roles(g.current_roles, ["Finance Admin"])


def list_jobs():
    _require_admin()
    jobs = _service().list_jobs()
    return jsonify(
        {
            "code": "ok",
            "message": "Jobs fetched.",
            "data": [
                {
                    "id": job.id,
                    "job_type": job.job_type,
                    "status": job.status,
                    "attempts": job.attempts,
                    "available_at": serialize_utc_datetime(job.available_at),
                    "last_error": job.last_error,
                }
                for job in jobs
            ],
        }
    )


def process_jobs():
    _require_admin()
    payload = request.get_json(silent=True) or request.form
    raw_count = payload.get("count") if payload else None
    if raw_count is None:
        raw_count = request.args.get("count", "1")
    try:
        count = int(raw_count)
    except (TypeError, ValueError) as exc:
        raise AppError("validation_error", "count must be an integer.", 400) from exc
    jobs = _service().process_jobs(count)
    return jsonify(
        {
            "code": "ok",
            "message": "Job processing complete.",
            "data": [
                {
                    "id": job.id,
                    "job_type": job.job_type,
                    "status": job.status,
                    "attempts": job.attempts,
                    "last_error": job.last_error,
                }
                for job in jobs
            ],
        }
    )


def list_rate_limits():
    _require_admin()
    buckets = _service().list_rate_limits()
    return jsonify({"code": "ok", "message": "Rate limits fetched.", "data": [{"bucket_key": bucket.bucket_key, "request_count": bucket.request_count} for bucket in buckets]})


def list_breakers():
    _require_admin()
    breakers = _service().list_breakers()
    return jsonify({"code": "ok", "message": "Circuit breakers fetched.", "data": [{"endpoint_key": breaker.endpoint_key, "state": breaker.state, "failure_count": breaker.failure_count} for breaker in breakers]})


def run_backup():
    _require_admin()
    job = _service().run_backup()
    return jsonify({"code": "ok", "message": "Backup completed.", "data": {"id": job.id, "file_path": job.file_path, "status": job.status}})


def test_restore():
    _require_admin()
    run = _service().restore_test()
    return jsonify({"code": "ok", "message": "Restore test completed.", "data": {"id": run.id, "restore_path": run.restore_path, "status": run.status}})
