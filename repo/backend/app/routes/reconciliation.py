from flask import Blueprint

from app.controllers.reconciliation_controller import (
    enqueue_reconciliation_import,
    get_run,
    import_reconciliation_csv,
    list_runs,
    reconciliation_dashboard,
    resolve_exception,
)


reconciliation_bp = Blueprint("reconciliation", __name__)

reconciliation_bp.get("/finance/reconciliation")(reconciliation_dashboard)
reconciliation_bp.post("/api/finance/reconciliation/import")(import_reconciliation_csv)
reconciliation_bp.post("/api/finance/reconciliation/import/async")(enqueue_reconciliation_import)
reconciliation_bp.get("/api/finance/reconciliation/runs")(list_runs)
reconciliation_bp.get("/api/finance/reconciliation/runs/<run_id>")(get_run)
reconciliation_bp.post("/api/finance/reconciliation/exceptions/<exception_id>/resolve")(resolve_exception)
