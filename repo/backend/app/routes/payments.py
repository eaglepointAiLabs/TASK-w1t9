from flask import Blueprint

from app.controllers.payment_controller import (
    capture_payment,
    finance_workspace,
    get_payment,
    import_callbacks,
    simulate_jsapi_callback,
    verify_callbacks,
)


payments_bp = Blueprint("payments", __name__)

payments_bp.get("/finance/payments")(finance_workspace)
payments_bp.post("/api/payments/capture")(capture_payment)
payments_bp.post("/api/payments/callbacks/import")(import_callbacks)
payments_bp.post("/api/payments/callbacks/verify")(verify_callbacks)
payments_bp.post("/api/payments/jsapi/simulate")(simulate_jsapi_callback)
payments_bp.get("/api/payments/<payment_id>")(get_payment)
