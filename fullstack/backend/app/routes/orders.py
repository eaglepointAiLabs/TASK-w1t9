from flask import Blueprint

from app.controllers.order_controller import (
    add_cart_item,
    cart_page,
    checkout,
    delete_cart_item,
    get_cart,
    get_order,
    update_cart_item,
)


orders_bp = Blueprint("orders", __name__)

orders_bp.get("/cart")(cart_page)
orders_bp.get("/api/cart")(get_cart)
orders_bp.post("/api/cart/items")(add_cart_item)
orders_bp.patch("/api/cart/items/<item_id>")(update_cart_item)
orders_bp.delete("/api/cart/items/<item_id>")(delete_cart_item)
orders_bp.post("/api/orders/checkout")(checkout)
orders_bp.get("/api/orders/<order_id>")(get_order)
