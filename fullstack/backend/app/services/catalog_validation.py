from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.services.errors import AppError
from app.services.time_utils import parse_iso_datetime_as_utc_naive


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_BYTES = 2 * 1024 * 1024


def parse_price(value: str | int | float | Decimal | None, field_name: str) -> Decimal:
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise AppError("validation_error", f"{field_name} must be a valid decimal.", 400)

    if price < 0:
        raise AppError("validation_error", f"{field_name} must be zero or greater.", 400)
    return price.quantize(Decimal("0.01"))


def normalize_slug(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace("&", "and")
        .replace("/", "-")
        .replace(" ", "-")
    )


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parse_iso_datetime_as_utc_naive(value)
    except ValueError:
        raise AppError("validation_error", "Invalid datetime format.", 400, {"value": value})


def validate_dish_payload(payload: dict) -> None:
    if not (payload.get("name") or "").strip():
        raise AppError("validation_error", "Dish name is required.", 400)

    parse_price(payload.get("base_price"), "base_price")
    if int(payload.get("stock_quantity", 0)) < 0:
        raise AppError("validation_error", "stock_quantity must be zero or greater.", 400)

    for window in payload.get("availability_windows", []):
        day = window.get("day_of_week")
        if day is None or int(day) < 0 or int(day) > 6:
            raise AppError("validation_error", "day_of_week must be between 0 and 6.", 400)
        start_time = window.get("start_time")
        end_time = window.get("end_time")
        if not start_time or not end_time:
            raise AppError("validation_error", "Availability windows require start_time and end_time.", 400)
        if start_time >= end_time:
            raise AppError("validation_error", "Availability window start_time must be before end_time.", 400)

    for option in payload.get("options", []):
        if not (option.get("name") or "").strip():
            raise AppError("validation_error", "Option group name is required.", 400)
        values = option.get("values", [])
        if not values:
            raise AppError("validation_error", "Each option group requires at least one value.", 400)
        for rule in option.get("rules", []):
            min_select = int(rule.get("min_select", 0))
            max_select = int(rule.get("max_select", 1))
            if min_select < 0 or max_select < 1 or min_select > max_select:
                raise AppError("validation_error", "Option rule selection bounds are invalid.", 400)
        for value in values:
            if not (value.get("label") or "").strip():
                raise AppError("validation_error", "Option value label is required.", 400)
            parse_price(value.get("price_delta", 0), "price_delta")


def validate_image_upload(content_type: str | None, size_bytes: int) -> None:
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise AppError(
            "invalid_image_type",
            "Only JPEG and PNG images are allowed.",
            400,
            {"allowed_types": sorted(ALLOWED_IMAGE_TYPES)},
        )
    if size_bytes > MAX_IMAGE_BYTES:
        raise AppError(
            "invalid_image_size",
            "Image must be 2 MB or smaller.",
            400,
            {"max_bytes": MAX_IMAGE_BYTES, "received_bytes": size_bytes},
        )
