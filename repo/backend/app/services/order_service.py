from __future__ import annotations

import json
from decimal import Decimal

import structlog
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models import CartItem, Dish
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.order_repository import OrderRepository
from app.services.catalog_service import CatalogService
from app.services.errors import AppError
from app.services.time_utils import utc_now_naive


logger = structlog.get_logger(__name__)


class OrderService:
    def __init__(self, repository: OrderRepository, catalog_repository: CatalogRepository) -> None:
        self.repository = repository
        self.catalog_repository = catalog_repository
        self.catalog_service = CatalogService(catalog_repository)

    def get_cart(self, user_id: str):
        cart = self.repository.get_cart(user_id)
        db.session.commit()
        return cart

    def add_cart_item(self, user_id: str, payload: dict):
        cart = self.repository.get_or_create_cart(user_id)
        dish_id = payload.get("dish_id")
        quantity = int(payload.get("quantity", 1))
        if quantity < 1:
            raise AppError("validation_error", "Quantity must be at least 1.", 400)

        pricing = self._build_pricing(dish_id, payload.get("selected_options", {}), quantity)
        item = self.repository.add_cart_item(
            cart_id=cart.id,
            dish_id=dish_id,
            quantity=quantity,
            selected_options_json=json.dumps(pricing["selected_options"]),
            unit_base_price=pricing["unit_base_price"],
            unit_options_price=pricing["unit_options_price"],
            unit_total_price=pricing["unit_total_price"],
            line_total_price=pricing["line_total_price"],
            pricing_breakdown_json=json.dumps(pricing["breakdown"]),
        )
        db.session.commit()
        logger.info("cart.item_added", user_id=user_id, cart_id=cart.id, cart_item_id=item.id, dish_id=dish_id)
        return item, cart

    def update_cart_item(self, user_id: str, item_id: str, payload: dict):
        cart = self.repository.get_cart(user_id)
        item = self.repository.get_cart_item(cart.id, item_id)
        if item is None:
            raise AppError("not_found", "Cart item not found.", 404)

        quantity = int(payload.get("quantity", item.quantity))
        if quantity < 1:
            raise AppError("validation_error", "Quantity must be at least 1.", 400)
        selected_options = payload.get("selected_options")
        if selected_options is None:
            selected_options = json.loads(item.selected_options_json)

        pricing = self._build_pricing(item.dish_id, selected_options, quantity)
        item.quantity = quantity
        item.selected_options_json = json.dumps(pricing["selected_options"])
        item.unit_base_price = pricing["unit_base_price"]
        item.unit_options_price = pricing["unit_options_price"]
        item.unit_total_price = pricing["unit_total_price"]
        item.line_total_price = pricing["line_total_price"]
        item.pricing_breakdown_json = json.dumps(pricing["breakdown"])
        db.session.add(item)
        db.session.commit()
        logger.info("cart.item_updated", user_id=user_id, cart_id=cart.id, cart_item_id=item.id)
        return item, cart

    def delete_cart_item(self, user_id: str, item_id: str):
        cart = self.repository.get_cart(user_id)
        item = self.repository.get_cart_item(cart.id, item_id)
        if item is None:
            raise AppError("not_found", "Cart item not found.", 404)
        self.repository.delete_cart_item(item)
        db.session.commit()
        logger.info("cart.item_removed", user_id=user_id, cart_id=cart.id, cart_item_id=item_id)
        return cart

    def checkout(self, user_id: str, checkout_key: str):
        if not checkout_key:
            raise AppError("validation_error", "checkout_key is required.", 400)

        existing = self.repository.find_order_by_checkout_key(user_id, checkout_key)
        if existing is not None:
            return existing

        cart = self.repository.get_cart(user_id)
        if not cart.items:
            raise AppError("validation_error", "Cart is empty.", 400)

        try:
            db.session.execute(db.text("BEGIN IMMEDIATE"))
        except OperationalError as exc:
            raise AppError(
                "checkout_busy",
                "Checkout is temporarily busy. Retry with the same checkout key.",
                409,
                {"reason": str(exc)},
            ) from exc

        existing = self.repository.find_order_by_checkout_key(user_id, checkout_key)
        if existing is not None:
            db.session.commit()
            return existing

        subtotal = Decimal("0.00")
        order = self.repository.create_order(
            user_id=user_id,
            cart_id=cart.id,
            checkout_key=checkout_key,
            status="submitted",
            subtotal_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            submitted_at=utc_now_naive(),
        )

        for cart_item in list(cart.items):
            dish = self.repository.get_dish_for_update(cart_item.dish_id)
            if dish is None or not dish.is_published or dish.archived_at is not None:
                raise AppError("dish_unavailable", "A cart item is no longer available.", 409)
            if dish.is_sold_out:
                raise AppError("dish_sold_out", f"{dish.name} is sold out.", 409)
            self._assert_dish_available_now(dish)
            selected_options = json.loads(cart_item.selected_options_json)
            pricing = self._build_pricing(dish.id, selected_options, cart_item.quantity)
            if dish.stock_quantity < cart_item.quantity:
                raise AppError(
                    "inventory_shortage",
                    f"{dish.name} no longer has enough stock.",
                    409,
                    {"requested": cart_item.quantity, "available": dish.stock_quantity},
                )
            dish.stock_quantity -= cart_item.quantity
            if dish.stock_quantity == 0:
                dish.is_sold_out = True
            db.session.add(dish)
            subtotal += pricing["line_total_price"]
            self.repository.add_order_item(
                order_id=order.id,
                dish_id=dish.id,
                dish_name=dish.name,
                quantity=cart_item.quantity,
                selected_options_json=json.dumps(pricing["selected_options"]),
                unit_base_price=pricing["unit_base_price"],
                unit_options_price=pricing["unit_options_price"],
                unit_total_price=pricing["unit_total_price"],
                line_total_price=pricing["line_total_price"],
                pricing_breakdown_json=json.dumps(pricing["breakdown"]),
            )
            self.repository.add_inventory_reservation(
                order_id=order.id,
                dish_id=dish.id,
                checkout_key=checkout_key,
                quantity=cart_item.quantity,
                status="consumed",
                note="Stock decremented at checkout submission.",
            )

        order.subtotal_amount = subtotal
        order.total_amount = subtotal
        db.session.add(order)
        self.repository.add_status_history(order.id, None, "submitted", "Checkout completed.")
        cart.status = "checked_out"
        db.session.add(cart)
        db.session.commit()
        logger.info("order.checkout_completed", user_id=user_id, order_id=order.id, checkout_key=checkout_key)
        return self.repository.find_order_by_checkout_key(user_id, checkout_key)

    def get_order(self, user_id: str, order_id: str):
        order = self.repository.get_order(order_id, user_id)
        if order is None:
            raise AppError("not_found", "Order not found.", 404)
        return order

    def _build_pricing(self, dish_id: str, selected_options: dict, quantity: int) -> dict:
        normalized = {
            key: value if isinstance(value, list) else [value]
            for key, value in selected_options.items()
        }
        validation = self.catalog_service.validate_required_options(dish_id, normalized)
        dish = self.catalog_repository.get_dish(dish_id)
        unit_base_price = Decimal(dish.base_price)
        unit_total_price = Decimal(validation["total_price"])
        unit_options_price = unit_total_price - unit_base_price
        line_total_price = unit_total_price * quantity
        breakdown = {
            "dish_name": dish.name,
            "base_price": f"{unit_base_price:.2f}",
            "options_total": f"{unit_options_price:.2f}",
            "unit_total": f"{unit_total_price:.2f}",
            "quantity": quantity,
            "selected_options": normalized,
        }
        return {
            "selected_options": normalized,
            "unit_base_price": unit_base_price,
            "unit_options_price": unit_options_price,
            "unit_total_price": unit_total_price,
            "line_total_price": line_total_price,
            "breakdown": breakdown,
        }

    def _assert_dish_available_now(self, dish: Dish) -> None:
        now = utc_now_naive()
        windows = [window for window in dish.availability_windows if window.is_enabled]
        if not windows:
            return
        weekday = now.weekday()
        current_time = now.time()
        if not any(window.day_of_week == weekday and window.start_time <= current_time < window.end_time for window in windows):
            raise AppError("dish_unavailable", f"{dish.name} is outside its availability window.", 409)
