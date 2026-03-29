from __future__ import annotations

import json
from uuid import uuid4

from flask import g, jsonify, render_template, request

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
    payload = request.get_json(silent=True) or _inflate_payload(request.form)
    item, cart = _service().add_cart_item(g.current_user.id, payload)
    if request.headers.get("HX-Request") == "true":
        return attach_feedback(
            (render_template("partials/cart_panel.html", cart=_serialize_cart(cart), checkout_key=str(uuid4())), 201),
            "Item added to cart.",
        )
    return jsonify({"code": "ok", "message": "Cart item added.", "data": _serialize_cart_item(item)}), 201


def update_cart_item(item_id: str):
    payload = request.get_json(silent=True) or _inflate_payload(request.form)
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
    payload = request.get_json(silent=True) or request.form
    order = _service().checkout(g.current_user.id, payload.get("checkout_key"))
    if request.headers.get("HX-Request") == "true":
        return attach_feedback(
            render_template("orders/confirmation.html", order=order, order_view=_serialize_order(order)),
            "Checkout completed.",
        )
    return jsonify({"code": "ok", "message": "Checkout completed.", "data": _serialize_order(order)})


def get_order(order_id: str):
    order = _service().get_order(g.current_user.id, order_id)
    if request.headers.get("HX-Request") == "true":
        return render_template("orders/confirmation.html", order=order, order_view=_serialize_order(order))
    return jsonify({"code": "ok", "message": "Order fetched.", "data": _serialize_order(order)})


def _inflate_payload(payload):
    data = payload.to_dict(flat=True)
    if "selected_options" in data and isinstance(data["selected_options"], str):
        data["selected_options"] = json.loads(data["selected_options"] or "{}")
    else:
        selected = {}
        for key in payload:
            if key.startswith("option_"):
                selected[key.removeprefix("option_")] = payload.getlist(key)
        data["selected_options"] = selected
    return data
