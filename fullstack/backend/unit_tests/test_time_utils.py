from datetime import UTC, datetime

from app.services.time_utils import (
    ensure_utc_naive,
    parse_iso_datetime_as_utc_naive,
    serialize_utc_datetime,
    utc_now_naive,
)


def test_utc_now_naive_returns_naive_datetime():
    value = utc_now_naive()

    assert value.tzinfo is None


def test_ensure_utc_naive_normalizes_offset_aware_values():
    value = ensure_utc_naive(datetime(2026, 3, 29, 15, 0, tzinfo=UTC))

    assert value == datetime(2026, 3, 29, 15, 0)
    assert value.tzinfo is None


def test_serialize_utc_datetime_returns_z_suffix():
    value = serialize_utc_datetime(datetime(2026, 3, 29, 15, 0))

    assert value == "2026-03-29T15:00:00Z"


def test_parse_iso_datetime_supports_trailing_z_suffix():
    value = parse_iso_datetime_as_utc_naive("2026-03-29T15:00:00Z")

    assert value == datetime(2026, 3, 29, 15, 0)
