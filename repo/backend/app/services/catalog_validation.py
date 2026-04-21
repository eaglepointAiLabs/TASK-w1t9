from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from app.services.errors import AppError
from app.services.time_utils import parse_iso_datetime_as_utc_naive


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_BYTES = 2 * 1024 * 1024

# Magic-byte signatures used to verify the declared MIME type matches the
# actual file content. Spoofed Content-Type headers must not pass validation.
_IMAGE_MAGIC_PREFIXES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


def parse_price(value: str | int | float | Decimal | None, field_name: str) -> Decimal:
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise AppError("validation_error", f"{field_name} must be a valid decimal.", 400)

    if price < 0:
        raise AppError("validation_error", f"{field_name} must be zero or greater.", 400)
    return price.quantize(Decimal("0.01"))


def parse_int(value, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise AppError("validation_error", f"{field_name} must be a valid integer.", 400)


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
    if parse_int(payload.get("stock_quantity", 0), "stock_quantity") < 0:
        raise AppError("validation_error", "stock_quantity must be zero or greater.", 400)

    for window in payload.get("availability_windows", []):
        day = window.get("day_of_week")
        if day is None:
            raise AppError("validation_error", "day_of_week must be between 0 and 6.", 400)
        day_int = parse_int(day, "day_of_week")
        if not 0 <= day_int <= 6:
            raise AppError("validation_error", "day_of_week must be between 0 and 6.", 400)
        start_time = window.get("start_time")
        end_time = window.get("end_time")
        if not start_time or not end_time:
            raise AppError("validation_error", "Availability windows require start_time and end_time.", 400)
        try:
            start_t = time.fromisoformat(str(start_time))
            end_t = time.fromisoformat(str(end_time))
        except ValueError:
            raise AppError("validation_error", "Availability window times must be valid HH:MM time strings.", 400)
        if start_t >= end_t:
            raise AppError("validation_error", "Availability window start_time must be before end_time.", 400)

    for option in payload.get("options", []):
        if not (option.get("name") or "").strip():
            raise AppError("validation_error", "Option group name is required.", 400)
        values = option.get("values", [])
        if not values:
            raise AppError("validation_error", "Each option group requires at least one value.", 400)
        for rule in option.get("rules", []):
            if not (rule.get("rule_type") or "").strip():
                raise AppError("validation_error", "Option rule_type is required.", 400)
            min_select = parse_int(rule.get("min_select", 0), "min_select")
            max_select = parse_int(rule.get("max_select", 1), "max_select")
            if min_select < 0 or max_select < 1 or min_select > max_select:
                raise AppError("validation_error", "Option rule selection bounds are invalid.", 400)
        for value in values:
            if not (value.get("label") or "").strip():
                raise AppError("validation_error", "Option value label is required.", 400)
            parse_price(value.get("price_delta", 0), "price_delta")


def validate_image_upload(content_type: str | None, content: bytes) -> None:
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise AppError(
            "invalid_image_type",
            "Only JPEG and PNG images are allowed.",
            400,
            {"allowed_types": sorted(ALLOWED_IMAGE_TYPES)},
        )
    size_bytes = len(content)
    if size_bytes > MAX_IMAGE_BYTES:
        raise AppError(
            "invalid_image_size",
            "Image must be 2 MB or smaller.",
            400,
            {"max_bytes": MAX_IMAGE_BYTES, "received_bytes": size_bytes},
        )
    # Trust the bytes, not the Content-Type header. A request can claim
    # image/jpeg while shipping arbitrary content; the magic-byte prefix is
    # what the decoder will ultimately see.
    prefixes = _IMAGE_MAGIC_PREFIXES.get(content_type, ())
    if not any(content.startswith(prefix) for prefix in prefixes):
        raise AppError(
            "invalid_image_content",
            "Uploaded file content does not match the declared image type.",
            400,
            {"declared_content_type": content_type},
        )
