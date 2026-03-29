from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class Cart(BaseModel):
    __tablename__ = "carts"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)
    items: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
    )


class CartItem(BaseModel):
    __tablename__ = "cart_items"

    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id"), nullable=False, index=True)
    dish_id: Mapped[str] = mapped_column(ForeignKey("dishes.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    selected_options_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    unit_base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_options_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    unit_total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    pricing_breakdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    cart: Mapped[Cart] = relationship("Cart", back_populates="items")


class Order(BaseModel):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("user_id", "checkout_key", name="uq_order_checkout_key"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    cart_id: Mapped[str | None] = mapped_column(ForeignKey("carts.id"), nullable=True, index=True)
    checkout_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="submitted", index=True)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(BaseModel):
    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    dish_id: Mapped[str] = mapped_column(ForeignKey("dishes.id"), nullable=False, index=True)
    dish_name: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_options_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    unit_base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_options_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    unit_total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    pricing_breakdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    order: Mapped[Order] = relationship("Order", back_populates="items")


class OrderStatusHistory(BaseModel):
    __tablename__ = "order_status_history"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    order: Mapped[Order] = relationship("Order", back_populates="status_history")


class InventoryReservation(BaseModel):
    __tablename__ = "inventory_reservations"

    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    dish_id: Mapped[str] = mapped_column(ForeignKey("dishes.id"), nullable=False, index=True)
    checkout_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True, default="reserved")
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")


__all__ = [
    "Cart",
    "CartItem",
    "InventoryReservation",
    "Order",
    "OrderItem",
    "OrderStatusHistory",
]
