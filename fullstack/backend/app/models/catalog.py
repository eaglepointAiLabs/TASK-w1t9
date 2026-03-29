from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class DishCategory(BaseModel):
    __tablename__ = "dish_categories"

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DishTag(BaseModel):
    __tablename__ = "dish_tags"

    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)


class Dish(BaseModel):
    __tablename__ = "dishes"

    category_id: Mapped[str | None] = mapped_column(ForeignKey("dish_categories.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_sold_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    category: Mapped[DishCategory | None] = relationship("DishCategory")
    tag_links: Mapped[list["DishTagMap"]] = relationship(
        "DishTagMap",
        back_populates="dish",
        cascade="all, delete-orphan",
    )
    availability_windows: Mapped[list["DishAvailabilityWindow"]] = relationship(
        "DishAvailabilityWindow",
        back_populates="dish",
        cascade="all, delete-orphan",
    )
    options: Mapped[list["DishOption"]] = relationship(
        "DishOption",
        back_populates="dish",
        cascade="all, delete-orphan",
    )
    images: Mapped[list["DishImage"]] = relationship(
        "DishImage",
        back_populates="dish",
        cascade="all, delete-orphan",
    )


class DishTagMap(BaseModel):
    __tablename__ = "dish_tag_map"
    __table_args__ = (UniqueConstraint("dish_id", "tag_id", name="uq_dish_tag"),)

    dish_id: Mapped[str] = mapped_column(ForeignKey("dishes.id"), nullable=False)
    tag_id: Mapped[str] = mapped_column(ForeignKey("dish_tags.id"), nullable=False)
    dish: Mapped[Dish] = relationship("Dish", back_populates="tag_links")
    tag: Mapped[DishTag] = relationship("DishTag")


class DishAvailabilityWindow(BaseModel):
    __tablename__ = "dish_availability_windows"

    dish_id: Mapped[str] = mapped_column(ForeignKey("dishes.id"), nullable=False, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dish: Mapped[Dish] = relationship("Dish", back_populates="availability_windows")


class DishOption(BaseModel):
    __tablename__ = "dish_options"

    dish_id: Mapped[str] = mapped_column(ForeignKey("dishes.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    display_type: Mapped[str] = mapped_column(String(40), nullable=False, default="single_select")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dish: Mapped[Dish] = relationship("Dish", back_populates="options")
    values: Mapped[list["DishOptionValue"]] = relationship(
        "DishOptionValue",
        back_populates="option",
        cascade="all, delete-orphan",
    )
    rules: Mapped[list["DishOptionRule"]] = relationship(
        "DishOptionRule",
        back_populates="option",
        cascade="all, delete-orphan",
    )


class DishOptionValue(BaseModel):
    __tablename__ = "dish_option_values"

    option_id: Mapped[str] = mapped_column(ForeignKey("dish_options.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    value_code: Mapped[str] = mapped_column(String(80), nullable=False)
    price_delta: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    option: Mapped[DishOption] = relationship("DishOption", back_populates="values")


class DishOptionRule(BaseModel):
    __tablename__ = "dish_option_rules"

    option_id: Mapped[str] = mapped_column(ForeignKey("dish_options.id"), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    min_select: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_select: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    option: Mapped[DishOption] = relationship("DishOption", back_populates="rules")


class DishImage(BaseModel):
    __tablename__ = "dish_images"

    dish_id: Mapped[str] = mapped_column(ForeignKey("dishes.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    alt_text: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dish: Mapped[Dish] = relationship("Dish", back_populates="images")


__all__ = [
    "Dish",
    "DishAvailabilityWindow",
    "DishCategory",
    "DishImage",
    "DishOption",
    "DishOptionRule",
    "DishOptionValue",
    "DishTag",
    "DishTagMap",
]
