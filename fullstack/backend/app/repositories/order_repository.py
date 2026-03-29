from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Cart,
    CartItem,
    Dish,
    DishAvailabilityWindow,
    DishOption,
    DishOptionRule,
    DishOptionValue,
    InventoryReservation,
    Order,
    OrderItem,
    OrderStatusHistory,
)


class OrderRepository:
    def get_or_create_cart(self, user_id: str) -> Cart:
        stmt = select(Cart).options(joinedload(Cart.items)).where(Cart.user_id == user_id, Cart.status == "active")
        cart = db.session.execute(stmt).unique().scalar_one_or_none()
        if cart is None:
            cart = Cart(user_id=user_id, status="active")
            db.session.add(cart)
            db.session.flush()
        return cart

    def get_cart(self, user_id: str) -> Cart:
        stmt = (
            select(Cart)
            .options(joinedload(Cart.items))
            .where(Cart.user_id == user_id, Cart.status == "active")
        )
        cart = db.session.execute(stmt).unique().scalar_one_or_none()
        if cart is None:
            return self.get_or_create_cart(user_id)
        return cart

    def get_cart_item(self, cart_id: str, item_id: str) -> CartItem | None:
        stmt = select(CartItem).where(CartItem.cart_id == cart_id, CartItem.id == item_id)
        return db.session.scalar(stmt)

    def add_cart_item(self, **kwargs) -> CartItem:
        item = CartItem(**kwargs)
        db.session.add(item)
        db.session.flush()
        return item

    def delete_cart_item(self, item: CartItem) -> None:
        db.session.delete(item)
        db.session.flush()

    def get_dish_for_update(self, dish_id: str) -> Dish | None:
        stmt = (
            select(Dish)
            .options(
                joinedload(Dish.options).joinedload(DishOption.values),
                joinedload(Dish.options).joinedload(DishOption.rules),
                joinedload(Dish.availability_windows),
            )
            .where(Dish.id == dish_id)
        )
        return db.session.execute(stmt).unique().scalar_one_or_none()

    def find_order_by_checkout_key(self, user_id: str, checkout_key: str) -> Order | None:
        stmt = (
            select(Order)
            .options(joinedload(Order.items), joinedload(Order.status_history))
            .where(Order.user_id == user_id, Order.checkout_key == checkout_key)
        )
        return db.session.execute(stmt).unique().scalar_one_or_none()

    def create_order(self, **kwargs) -> Order:
        order = Order(**kwargs)
        db.session.add(order)
        db.session.flush()
        return order

    def add_order_item(self, **kwargs) -> OrderItem:
        item = OrderItem(**kwargs)
        db.session.add(item)
        db.session.flush()
        return item

    def add_status_history(self, order_id: str, from_status: str | None, to_status: str, note: str) -> None:
        db.session.add(OrderStatusHistory(order_id=order_id, from_status=from_status, to_status=to_status, note=note))
        db.session.flush()

    def add_inventory_reservation(
        self,
        order_id: str | None,
        dish_id: str,
        checkout_key: str,
        quantity: int,
        status: str,
        note: str,
    ) -> InventoryReservation:
        reservation = InventoryReservation(
            order_id=order_id,
            dish_id=dish_id,
            checkout_key=checkout_key,
            quantity=quantity,
            status=status,
            note=note,
        )
        db.session.add(reservation)
        db.session.flush()
        return reservation

    def get_order(self, order_id: str, user_id: str) -> Order | None:
        stmt = (
            select(Order)
            .options(joinedload(Order.items), joinedload(Order.status_history))
            .where(Order.id == order_id, Order.user_id == user_id)
        )
        return db.session.execute(stmt).unique().scalar_one_or_none()
