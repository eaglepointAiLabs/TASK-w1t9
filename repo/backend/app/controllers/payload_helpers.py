from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import request

from app.services.errors import AppError


def require_dict_payload(label: str = "Request body") -> Mapping[str, Any]:
    """
    Return the current request body as a dict-like mapping, rejecting
    anything that is not a JSON object or a form-encoded body.

    - JSON object body → returned as-is.
    - Form-encoded body → ImmutableMultiDict (a Mapping) is returned.
    - JSON array / string / number / null, or a Content-Type: application/json
      body that fails to parse → AppError(400, "validation_error").

    Service code downstream assumes a Mapping; this check is the boundary
    guard that prevents a 500 when the caller ships the wrong shape.
    """
    if request.is_json:
        payload = request.get_json(silent=True)
        if not isinstance(payload, Mapping):
            raise AppError("validation_error", f"{label} must be a JSON object.", 400)
        return payload
    return request.form


def require_dict_field(
    payload: Mapping[str, Any],
    field: str,
    *,
    optional: bool = True,
    label: str | None = None,
) -> dict:
    """Ensure a nested field is a dict. Returns {} when optional and missing."""
    name = label or field
    value = payload.get(field)
    if value is None:
        if optional:
            return {}
        raise AppError("validation_error", f"{name} is required.", 400)
    if not isinstance(value, dict):
        raise AppError("validation_error", f"{name} must be a JSON object.", 400)
    return value


def require_list_field(
    payload: Mapping[str, Any],
    field: str,
    *,
    optional: bool = True,
    label: str | None = None,
) -> list:
    """Ensure a nested field is a list. Returns [] when optional and missing."""
    name = label or field
    value = payload.get(field)
    if value is None:
        if optional:
            return []
        raise AppError("validation_error", f"{name} is required.", 400)
    if not isinstance(value, list):
        raise AppError("validation_error", f"{name} must be an array.", 400)
    return value
