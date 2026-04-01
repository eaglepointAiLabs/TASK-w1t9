from flask import Blueprint

from app.controllers.ops_controller import list_breakers, list_jobs, list_rate_limits, process_jobs, run_backup, test_restore


ops_bp = Blueprint("ops", __name__)

ops_bp.get("/api/admin/ops/jobs")(list_jobs)
ops_bp.post("/api/admin/ops/jobs/process")(process_jobs)
ops_bp.get("/api/admin/ops/rate-limits")(list_rate_limits)
ops_bp.get("/api/admin/ops/circuit-breakers")(list_breakers)
ops_bp.post("/api/admin/ops/backups/run")(run_backup)
ops_bp.post("/api/admin/ops/restore/test")(test_restore)
