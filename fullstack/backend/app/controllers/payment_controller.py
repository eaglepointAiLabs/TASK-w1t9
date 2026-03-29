from __future__ import annotations

import json

from flask import g, jsonify, render_template, request

from app.controllers.ui_helpers import attach_feedback, redirect_anonymous_to_login
from app.repositories.payment_repository import PaymentRepository
from app.services.payment_service import PaymentService
from app.services.time_utils import serialize_utc_datetime


def _service():
    return PaymentService(PaymentRepository())


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


def finance_workspace():
    redirect_response = redirect_anonymous_to_login()
    if redirect_response is not None:
        return redirect_response
    payments, keys = _service().list_workspace(g.current_roles)
    return render_template("finance/workspace.html", payments=payments, keys=keys)


def capture_payment():
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
    payment = _service().capture_payment(payload, g.current_roles)
    if request.headers.get("HX-Request") == "true":
        payments, keys = _service().list_workspace(g.current_roles)
        return attach_feedback(render_template("finance/workspace.html", payments=payments, keys=keys), "Payment capture recorded.")
    return jsonify({"code": "ok", "message": "Payment capture recorded.", "data": _serialize_payment(payment)}), 201


def import_callbacks():
    payload = request.get_json(silent=True)
    if payload is None and "package_file" in request.files:
        payload = json.loads(request.files["package_file"].read().decode("utf-8"))
    elif payload is None:
        payload = json.loads(request.form.get("package_json", "{}"))
    response = _service().import_callback(payload, g.current_roles)
    if request.headers.get("HX-Request") == "true":
        payments, keys = _service().list_workspace(g.current_roles)
        tone = "success" if response["code"] == "ok" else "warning"
        return attach_feedback(render_template("finance/workspace.html", payments=payments, keys=keys), response["message"], tone=tone)
    return jsonify(response), 200 if response["code"] == "ok" else 409


def verify_callbacks():
    payload = request.get_json(silent=True)
    if payload is None and "package_file" in request.files:
        payload = json.loads(request.files["package_file"].read().decode("utf-8"))
    elif payload is None:
        payload = json.loads(request.form.get("package_json", "{}"))
    verification = _service().verify_callback_preview(payload, g.current_roles)
    return jsonify({"code": "ok", "message": "Callback verification complete.", "data": verification})


def get_payment(payment_id: str):
    payment = _service().get_payment(payment_id, g.current_roles)
    return jsonify({"code": "ok", "message": "Payment fetched.", "data": _serialize_payment(payment)})
