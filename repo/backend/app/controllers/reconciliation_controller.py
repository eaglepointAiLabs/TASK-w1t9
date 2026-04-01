from __future__ import annotations

import json

from flask import g, jsonify, render_template, request

from app.controllers.ui_helpers import attach_feedback, redirect_anonymous_to_login
from app.repositories.reconciliation_repository import ReconciliationRepository
from app.services.errors import AppError
from app.services.reconciliation_service import ReconciliationService
from app.services.time_utils import serialize_utc_datetime


def _service():
    return ReconciliationService(ReconciliationRepository())


def _require_authenticated_user():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)


def _serialize_exception(exception):
    return {
        "id": exception.id,
        "transaction_reference": exception.transaction_reference,
        "exception_type": exception.exception_type,
        "status": exception.status,
        "details": json.loads(exception.details_json),
        "resolution_reason": exception.resolution_reason,
        "resolved_at": serialize_utc_datetime(exception.resolved_at),
        "actions": [
            {
                "id": action.id,
                "action_type": action.action_type,
                "from_status": action.from_status,
                "to_status": action.to_status,
                "reason": action.reason,
            }
            for action in exception.actions
        ],
    }


def _serialize_run(run):
    return {
        "id": run.id,
        "source_name": run.source_name,
        "status": run.status,
        "total_rows": run.total_rows,
        "matched_rows": run.matched_rows,
        "exception_count": run.exception_count,
        "imported_filename": run.imported_filename,
        "rows": [
            {
                "id": row.id,
                "row_number": row.row_number,
                "transaction_reference": row.transaction_reference,
                "terminal_status": row.terminal_status,
                "terminal_amount": f"{row.terminal_amount:.2f}",
                "terminal_currency": row.terminal_currency,
                "match_status": row.match_status,
            }
            for row in run.rows
        ],
        "exceptions": [_serialize_exception(exception) for exception in run.exceptions],
    }


def reconciliation_dashboard():
    redirect_response = redirect_anonymous_to_login()
    if redirect_response is not None:
        return redirect_response
    runs = _service().list_runs(g.current_roles)
    return render_template("reconciliation/dashboard.html", runs=runs)


def import_reconciliation_csv():
    _require_authenticated_user()
    csv_text, filename, source_name, async_requested = _parse_import_payload()
    if async_requested:
        job = _service().enqueue_import_csv(
            csv_text=csv_text,
            source_name=source_name,
            imported_filename=filename,
            operator_user_id=g.current_user.id,
            current_roles=g.current_roles,
        )
        return (
            jsonify(
                {
                    "code": "accepted",
                    "message": "Reconciliation import queued.",
                    "data": {"job_id": job.id, "status": job.status},
                }
            ),
            202,
        )

    run = _service().import_csv(
        csv_text=csv_text,
        source_name=source_name,
        imported_filename=filename,
        operator_user_id=g.current_user.id,
        current_roles=g.current_roles,
    )
    if request.headers.get("HX-Request") == "true":
        return attach_feedback((render_template("reconciliation/run_detail.html", run=run), 201), "Statement imported.")
    return jsonify({"code": "ok", "message": "Reconciliation run imported.", "data": _serialize_run(run)}), 201


def enqueue_reconciliation_import():
    _require_authenticated_user()
    csv_text, filename, source_name, _async_requested = _parse_import_payload()
    job = _service().enqueue_import_csv(
        csv_text=csv_text,
        source_name=source_name,
        imported_filename=filename,
        operator_user_id=g.current_user.id,
        current_roles=g.current_roles,
    )
    return (
        jsonify(
            {
                "code": "accepted",
                "message": "Reconciliation import queued.",
                "data": {"job_id": job.id, "status": job.status},
            }
        ),
        202,
    )


def list_runs():
    runs = _service().list_runs(g.current_roles)
    return jsonify(
        {
            "code": "ok",
            "message": "Reconciliation runs fetched.",
            "data": [
                {
                    "id": run.id,
                    "status": run.status,
                    "source_name": run.source_name,
                    "total_rows": run.total_rows,
                    "matched_rows": run.matched_rows,
                    "exception_count": run.exception_count,
                }
                for run in runs
            ],
        }
    )


def get_run(run_id: str):
    run = _service().get_run(run_id, g.current_roles)
    if request.headers.get("HX-Request") == "true":
        return render_template("reconciliation/run_detail.html", run=run)
    return jsonify({"code": "ok", "message": "Reconciliation run fetched.", "data": _serialize_run(run)})


def resolve_exception(exception_id: str):
    _require_authenticated_user()
    payload = request.get_json(silent=True) or request.form
    exception = _service().resolve_exception(
        exception_id=exception_id,
        action_type=(payload.get("action_type") or "resolve").strip(),
        reason=(payload.get("reason") or "").strip(),
        operator_user_id=g.current_user.id,
        current_roles=g.current_roles,
    )
    run = _service().get_run(exception.run_id, g.current_roles)
    if request.headers.get("HX-Request") == "true":
        return attach_feedback(render_template("reconciliation/run_detail.html", run=run), "Exception resolved.")
    return jsonify({"code": "ok", "message": "Reconciliation exception updated.", "data": _serialize_exception(exception)})


def _parse_import_payload():
    json_payload = request.get_json(silent=True) or {}
    if "statement_file" in request.files:
        csv_text = request.files["statement_file"].read().decode("utf-8")
        filename = request.files["statement_file"].filename or ""
    elif json_payload:
        csv_text = json_payload.get("statement_csv", "")
        filename = json_payload.get("filename", "")
    else:
        csv_text = request.form.get("statement_csv", "")
        filename = request.form.get("filename", "")

    source_name = request.form.get("source_name") or json_payload.get("source_name", "terminal_csv")
    async_value = request.form.get("async") if request.form else None
    if async_value is None and isinstance(json_payload, dict):
        async_value = json_payload.get("async")
    async_requested = str(async_value).strip().lower() in {"1", "true", "yes", "on"}
    return csv_text, filename, source_name, async_requested
