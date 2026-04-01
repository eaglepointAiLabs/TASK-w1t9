from __future__ import annotations

from flask import g, jsonify, render_template, request

from app.controllers.ui_helpers import attach_feedback, redirect_anonymous_to_login
from app.repositories.moderation_repository import ModerationRepository
from app.services.errors import AppError
from app.services.moderation_service import ModerationService
from app.services.rbac_service import RBACService


def _service():
    return ModerationService(ModerationRepository())


def _serialize_item(item):
    return {
        "id": item.id,
        "report_id": item.report_id,
        "target_type": item.target_type,
        "target_id": item.target_id,
        "status": item.status,
        "priority": item.priority,
        "latest_reason_code": item.latest_reason_code,
        "notes": item.notes,
        "history": [
            {
                "id": action.id,
                "reason_code": action.reason_code,
                "outcome": action.outcome,
                "operator_notes": action.operator_notes,
                "from_status": action.from_status,
                "to_status": action.to_status,
            }
            for action in item.actions
        ],
    }


def moderation_page():
    redirect_response = redirect_anonymous_to_login()
    if redirect_response is not None:
        return redirect_response
    status = request.args.get("status")
    items = _service().list_queue(g.current_roles, status=status)
    reason_codes = ModerationRepository().list_reason_codes()
    return render_template("moderation/queue.html", items=items, reason_codes=reason_codes, status=status)


def get_queue():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    status = request.args.get("status")
    items = _service().list_queue(g.current_roles, status=status)
    return jsonify({"code": "ok", "message": "Moderation queue fetched.", "data": [_serialize_item(item) for item in items]})


def decide_item(item_id: str):
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    payload = request.get_json(silent=True) or request.form
    item = _service().decide_item(item_id, payload, g.current_user, g.current_roles)
    if request.headers.get("HX-Request") == "true":
        reason_codes = ModerationRepository().list_reason_codes()
        items = _service().list_queue(g.current_roles, status=request.args.get("status"))
        return attach_feedback(
            render_template("moderation/queue.html", items=items, reason_codes=reason_codes, status=request.args.get("status")),
            "Moderation decision recorded.",
        )
    return jsonify({"code": "ok", "message": "Moderation decision recorded.", "data": _serialize_item(item)})


def get_history(item_id: str):
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    item = _service().get_history(item_id, g.current_roles)
    if request.headers.get("HX-Request") == "true":
        return render_template("moderation/history.html", item=item)
    return jsonify({"code": "ok", "message": "Moderation history fetched.", "data": _serialize_item(item)})


def admin_page():
    redirect_response = redirect_anonymous_to_login()
    if redirect_response is not None:
        return redirect_response
    RBACService().require_roles(g.current_roles, ["Finance Admin"])
    return render_template("admin/roles.html", role_change_event=None)


def change_role():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    payload = request.get_json(silent=True) or request.form
    event = _service().change_role(
        payload,
        g.current_user,
        g.current_roles,
        g.current_session.id if g.current_session else None,
        payload.get("nonce"),
    )
    if request.headers.get("HX-Request") == "true":
        return attach_feedback(render_template("partials/role_change_status.html", role_change_event=event), "Role change applied.")
    if not request.is_json:
        return render_template("admin/roles.html", role_change_event=event)
    return jsonify(
        {
            "code": "ok",
            "message": "Role change applied.",
            "data": {
                "id": event.id,
                "role_name": event.role_name,
                "action": event.action,
                "status": event.status,
            },
        }
    )
