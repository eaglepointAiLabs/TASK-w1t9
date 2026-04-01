from flask import Blueprint

from app.controllers.refund_controller import confirm_stepup, create_refund, get_refund, list_risk_events, refund_page


refunds_bp = Blueprint("refunds", __name__)

refunds_bp.get("/finance/refunds")(refund_page)
refunds_bp.post("/api/refunds")(create_refund)
refunds_bp.get("/api/refunds/<refund_id>")(get_refund)
refunds_bp.post("/api/refunds/<refund_id>/confirm-stepup")(confirm_stepup)
refunds_bp.get("/api/refunds/risk-events")(list_risk_events)
