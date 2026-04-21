from __future__ import annotations

import json
from uuid import uuid4

from flask import g, jsonify, render_template, request

from app.controllers.pagination import paginate_collection, parse_pagination_args
from app.controllers.payload_helpers import require_dict_field, require_dict_payload
from app.controllers.ui_helpers import attach_feedback, redirect_anonymous_to_login
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.order_repository import OrderRepository
from app.services.errors import AppError
from app.services.order_service import OrderService
from app.services.time_utils import serialize_utc_datetime


def _service():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    return OrderService(OrderRepository(), CatalogRepository())


def _serialize_cart_item(item):
    return {
        "id": item.id,
        "dish_id": item.dish_id,
        "quantity": item.quantity,
        "selected_options": json.loads(item.selected_options_json),
        "unit_base_price": f"{item.unit_base_price:.2f}",
        "unit_options_price": f"{item.unit_options_price:.2f}",
        "unit_total_price": f"{item.unit_total_price:.2f}",
        "line_total_price": f"{item.line_total_price:.2f}",
        "pricing_breakdown": json.loads(item.pricing_breakdown_json),
    }


def _serialize_cart(cart):
    return {
        "id": cart.id,
        "status": cart.status,
        "items": [_serialize_cart_item(item) for item in cart.items],
        "total_amount": f"{sum(item.line_total_price for item in cart.items):.2f}",
    }


def _serialize_order(order):
    return {
        "id": order.id,
        "status": order.status,
        "checkout_key": order.checkout_key,
        "subtotal_amount": f"{order.subtotal_amount:.2f}",
        "total_amount": f"{order.total_amount:.2f}",
        "submitted_at": serialize_utc_datetime(order.submitted_at),
        "items": [
            {
                "id": item.id,
                "dish_id": item.dish_id,
                "dish_name": item.dish_name,
                "quantity": item.quantity,
                "selected_options": json.loads(item.selected_options_json),
                "unit_base_price": f"{item.unit_base_price:.2f}",
                "unit_options_price": f"{item.unit_options_price:.2f}",
                "unit_total_price": f"{item.unit_total_price:.2f}",
                "line_total_price": f"{item.line_total_price:.2f}",
                "pricing_breakdown": json.loads(item.pricing_breakdown_json),
            }
            for item in order.items
        ],
    }


def cart_page():
    redirect_response = redirect_anonymous_to_login()
    if redirect_response is not None:
        return redirect_response
    cart = _service().get_cart(g.current_user.id)
    return render_template("cart/index.html", cart=_serialize_cart(cart), checkout_key=str(uuid4()))


def get_cart():
    cart = _service().get_cart(g.current_user.id)
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/cart_panel.html", cart=_serialize_cart(cart), checkout_key=str(uuid4()))
    return jsonify({"code": "ok", "message": "Cart fetched.", "data": _serialize_cart(cart)})


def add_cart_item():
    payload = _resolve_cart_payload()
    item, cart = _service().add_cart_item(g.current_user.id, payload)
    if request.headers.get("HX-Request") == "true":
        return attach_feedback(
            (render_template("partials/cart_panel.html", cart=_serialize_cart(cart), checkout_key=str(uuid4())), 201),
            "Item added to cart.",
        )
    return jsonify({"code": "ok", "message": "Cart item added.", "data": _serialize_cart_item(item)}), 201


def update_cart_item(item_id: str):
    payload = _resolve_cart_payload()
    item, cart = _service().update_cart_item(g.current_user.id, item_id, payload)
    if request.headers.get("HX-Request") == "true":
        return attach_feedback(
            render_template("partials/cart_panel.html", cart=_serialize_cart(cart), checkout_key=str(uuid4())),
            "Cart updated.",
        )
    return jsonify({"code": "ok", "message": "Cart item updated.", "data": _serialize_cart_item(item)})


def delete_cart_item(item_id: str):
    cart = _service().delete_cart_item(g.current_user.id, item_id)
    if request.headers.get("HX-Request") == "true":
        return attach_feedback(
            render_template("partials/cart_panel.html", cart=_serialize_cart(cart), checkout_key=str(uuid4())),
            "Item removed from cart.",
        )
    return jsonify({"code": "ok", "message": "Cart item removed.", "data": {}})


def checkout():
    if request.is_json:
        payload = require_dict_payload()
    else:
        payload = request.form
    order = _service().checkout(g.current_user.id, payload.get("checkout_key"))
    if request.headers.get("HX-Request") == "true":
        return attach_feedback(
            render_template("orders/confirmation.html", order=order, order_view=_serialize_order(order)),
            "Checkout completed.",
        )
    return jsonify({"code": "ok", "message": "Checkout completed.", "data": _serialize_order(order)})


def list_orders():
    orders = _service().list_orders(g.current_user.id)
    pagination = parse_pagination_args(request.args)
    page_orders, pagination_meta = paginate_collection(orders, pagination)
    return jsonify(
        {
            "code": "ok",
            "message": "Orders fetched.",
            "data": [_serialize_order(order) for order in page_orders],
            "pagination": pagination_meta,
        }
    )


def get_order(order_id: str):
    order = _service().get_order(g.current_user.id, order_id)
    if request.headers.get("HX-Request") == "true":
        return render_template("orders/confirmation.html", order=order, order_view=_serialize_order(order))
    return jsonify({"code": "ok", "message": "Order fetched.", "data": _serialize_order(order)})


def _resolve_cart_payload() -> dict:
    """
    Accept either a JSON object or a form body and return a dict. Reject
    JSON arrays / strings / null up front so services never see a
    wrong-shaped payload, and confirm nested selected_options is itself
    an object when present.
    """
    if request.is_json:
        payload = dict(require_dict_payload())
    else:
        payload = _inflate_payload(request.form)
    if "selected_options" in payload and payload["selected_options"] is not None:
        # _inflate_payload coerces form-encoded selected_options into a dict;
        # for JSON bodies we must explicitly reject non-object shapes.
        require_dict_field(payload, "selected_options", label="selected_options")
    return payload


def _inflate_payload(payload):
    data = payload.to_dict(flat=True)
    if "selected_options" in data and isinstance(data["selected_options"], str):
        try:
            data["selected_options"] = json.loads(data["selected_options"] or "{}")
        except json.JSONDecodeError as exc:
            raise AppError("validation_error", "selected_options must contain valid JSON.", 400) from exc
    else:
        selected = {}
        for key in payload:
            if key.startswith("option_"):
                selected[key.removeprefix("option_")] = payload.getlist(key)
        data["selected_options"] = selected
    return data
