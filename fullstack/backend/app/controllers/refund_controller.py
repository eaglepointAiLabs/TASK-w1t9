from __future__ import annotations

import json

from flask import g, jsonify, render_template, request

from app.controllers.ui_helpers import attach_feedback, redirect_anonymous_to_login
from app.repositories.refund_repository import RefundRepository
from app.services.errors import AppError
from app.services.rbac_service import RBACService
from app.services.refund_service import RefundService
from app.services.time_utils import serialize_utc_datetime


def _service():
    return RefundService(RefundRepository())


def _serialize_refund(refund):
    return {
        "id": refund.id,
        "refund_reference": refund.refund_reference,
        "transaction_reference": refund.transaction_reference,
        "requested_amount": f"{refund.requested_amount:.2f}",
        "status": refund.status,
        "hold_reason": refund.hold_reason,
        "stepup_required": refund.stepup_required == "true",
        "approved_at": serialize_utc_datetime(refund.approved_at),
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "details": json.loads(event.details_json),
            }
            for event in refund.events
        ],
    }


def refund_page():
    redirect_response = redirect_anonymous_to_login()
    if redirect_response is not None:
        return redirect_response
    RBACService().require_roles(g.current_roles, ["Finance Admin"])
    return render_template("finance/refunds.html")


def create_refund():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    payload = request.get_json(silent=True) or request.form
    refund = _service().create_refund(
        payload=payload,
        current_user=g.current_user,
        current_roles=g.current_roles,
        current_session_id=g.current_session.id if g.current_session else None,
        nonce_value=payload.get("nonce"),
        device_id=request.headers.get("X-Device-Id") or g.client_id,
    )
    if request.headers.get("HX-Request") == "true":
        return attach_feedback(render_template("partials/refund_status.html", refund=refund), "Refund request submitted.")
    return jsonify({"code": "ok", "message": "Refund created.", "data": _serialize_refund(refund)}), 201


def get_refund(refund_id: str):
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    refund = _service().get_refund(refund_id, g.current_roles)
    return jsonify({"code": "ok", "message": "Refund fetched.", "data": _serialize_refund(refund)})


def confirm_stepup(refund_id: str):
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    payload = request.get_json(silent=True) or request.form
    refund = _service().confirm_stepup(
        refund_id=refund_id,
        password=payload.get("password") or "",
        current_user=g.current_user,
        current_roles=g.current_roles,
        current_session_id=g.current_session.id if g.current_session else None,
        nonce_value=payload.get("nonce"),
    )
    if request.headers.get("HX-Request") == "true":
        return attach_feedback(render_template("partials/refund_status.html", refund=refund), "Step-up confirmed.")
    return jsonify({"code": "ok", "message": "Refund step-up confirmed.", "data": _serialize_refund(refund)})


def list_risk_events():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    events = _service().list_risk_events(g.current_roles)
    return jsonify(
        {
            "code": "ok",
            "message": "Refund risk events fetched.",
            "data": [
                {
                    "id": event.id,
                    "refund_id": event.refund_id,
                    "payment_transaction_id": event.payment_transaction_id,
                    "device_id": event.device_id,
                    "risk_code": event.risk_code,
                    "severity": event.severity,
                    "action_taken": event.action_taken,
                }
                for event in events
            ],
        }
    )
