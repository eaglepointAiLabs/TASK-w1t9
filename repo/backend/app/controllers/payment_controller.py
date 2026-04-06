from __future__ import annotations

import json

from flask import g, jsonify, render_template, request

from app.controllers.pagination import paginate_collection, parse_pagination_args
from app.controllers.ui_helpers import attach_feedback, redirect_anonymous_to_login
from app.repositories.payment_repository import PaymentRepository
from app.services.errors import AppError
from app.services.payment_service import PaymentService
from app.services.time_utils import serialize_utc_datetime


def _service():
    return PaymentService(PaymentRepository())


def _require_authenticated_user():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)


def _serialize_payment(payment):
    return {
        "id": payment.id,
        "order_id": payment.order_id,
        "transaction_reference": payment.transaction_reference,
        "channel": payment.channel,
        "capture_amount": f"{payment.capture_amount:.2f}",
        "currency": payment.currency,
        "status": payment.status,
        "source": payment.source,
        "captured_at": serialize_utc_datetime(payment.captured_at),
        "failure_reason": payment.failure_reason,
        "callbacks": [
            {
                "id": callback.id,
                "verification_status": callback.verification_status,
                "verification_message": callback.verification_message,
                "payload_hash": callback.payload_hash,
                "key_id": callback.key_id,
            }
            for callback in payment.callbacks
        ],
    }


def _render_workspace(payments, keys, verification=None, simulation=None):
    return render_template(
        "finance/workspace.html",
        payments=payments,
        keys=keys,
        verification=verification,
        simulation=simulation,
    )


def finance_workspace():
    redirect_response = redirect_anonymous_to_login()
    if redirect_response is not None:
        return redirect_response
    payments, keys = _service().list_workspace(g.current_roles)
    return _render_workspace(payments, keys)


def capture_payment():
    _require_authenticated_user()
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
    payment = _service().capture_payment(payload, g.current_roles)
    if request.headers.get("HX-Request") == "true":
        payments, keys = _service().list_workspace(g.current_roles)
        return attach_feedback(_render_workspace(payments, keys), "Payment capture recorded.")
    return jsonify({"code": "ok", "message": "Payment capture recorded.", "data": _serialize_payment(payment)}), 201


def import_callbacks():
    _require_authenticated_user()
    payload = _load_callback_payload()
    response = _service().import_callback(payload, g.current_roles)
    if request.headers.get("HX-Request") == "true":
        payments, keys = _service().list_workspace(g.current_roles)
        tone = "success" if response["code"] == "ok" else "warning"
        return attach_feedback(_render_workspace(payments, keys), response["message"], tone=tone)
    return jsonify(response), 200 if response["code"] == "ok" else 409


def verify_callbacks():
    _require_authenticated_user()
    payload = _load_callback_payload()
    verification = _service().verify_callback_preview(payload, g.current_roles)
    if request.headers.get("HX-Request") == "true":
        payments, keys = _service().list_workspace(g.current_roles)
        tone = "success" if verification["verified"] else "warning"
        message = "Callback verification preview generated." if verification["verified"] else verification["message"]
        return attach_feedback(_render_workspace(payments, keys, verification=verification), message, tone=tone)
    return jsonify({"code": "ok", "message": "Callback verification complete.", "data": verification})


def simulate_jsapi_callback():
    _require_authenticated_user()
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
    result = _service().simulate_jsapi_callback(payload, g.current_roles)
    status_code = 200 if result["import_result"]["code"] == "ok" else 409
    if request.headers.get("HX-Request") == "true":
        payments, keys = _service().list_workspace(g.current_roles)
        tone = "success" if result["import_result"]["code"] == "ok" else "warning"
        return attach_feedback(
            _render_workspace(payments, keys, simulation=result),
            "JSAPI simulator callback processed.",
            tone=tone,
        )
    return (
        jsonify(
            {
                "code": result["import_result"]["code"],
                "message": "JSAPI simulator callback processed.",
                "data": result,
            }
        ),
        status_code,
    )


def list_payments():
    _require_authenticated_user()
    payments, _keys = _service().list_workspace(g.current_roles)
    pagination = parse_pagination_args(request.args)
    page_payments, pagination_meta = paginate_collection(payments, pagination)
    return jsonify(
        {
            "code": "ok",
            "message": "Payments fetched.",
            "data": [_serialize_payment(payment) for payment in page_payments],
            "pagination": pagination_meta,
        }
    )


def get_payment(payment_id: str):
    _require_authenticated_user()
    payment = _service().get_payment(payment_id, g.current_roles)
    return jsonify({"code": "ok", "message": "Payment fetched.", "data": _serialize_payment(payment)})


def _load_callback_payload():
    payload = request.get_json(silent=True)
    if payload is not None:
        return payload
    if "package_file" in request.files:
        try:
            return json.loads(request.files["package_file"].read().decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AppError("validation_error", "package_file must contain valid JSON.", 400, {"error": str(exc)}) from exc
    raw_package = request.form.get("package_json", "{}")
    try:
        return json.loads(raw_package)
    except json.JSONDecodeError as exc:
        raise AppError("validation_error", "package_json must contain valid JSON.", 400, {"error": str(exc)}) from exc
