from datetime import datetime

import pytest

from app.repositories.catalog_repository import CatalogRepository
from app.services.catalog_service import CatalogService
from app.services.errors import AppError


def test_availability_window_filtering_excludes_closed_dishes(app):
    service = CatalogService(CatalogRepository())

    monday_noon = "2026-03-30T12:00"
    tuesday_noon = "2026-03-31T12:00"

    monday_dishes = service.list_dishes(available_at=monday_noon)
    tuesday_dishes = service.list_dishes(available_at=tuesday_noon)

    monday_names = {dish.name for dish in monday_dishes}
    tuesday_names = {dish.name for dish in tuesday_dishes}

    assert "Signature Beef Noodles" in monday_names
    assert "Signature Beef Noodles" not in tuesday_names


def test_availability_window_filtering_accepts_offset_aware_timestamp(app):
    service = CatalogService(CatalogRepository())

    monday_noon_utc = "2026-03-30T12:00:00+00:00"
    monday_evening_eat = "2026-03-30T15:00:00+03:00"

    utc_dishes = service.list_dishes(available_at=monday_noon_utc)
    offset_dishes = service.list_dishes(available_at=monday_evening_eat)

    utc_names = {dish.name for dish in utc_dishes}
    offset_names = {dish.name for dish in offset_dishes}

    assert "Signature Beef Noodles" in utc_names
    assert utc_names == offset_names


def test_required_option_enforcement(app):
    repository = CatalogRepository()
    dish = repository.get_dish_by_slug("signature-beef-noodles")

    with pytest.raises(AppError) as exc:
        CatalogService(repository).validate_required_options(dish.id, {"spice_level": ["mild"]})

    assert exc.value.code == "required_options_missing"


def test_required_option_success_returns_total(app):
    repository = CatalogRepository()
    dish = repository.get_dish_by_slug("signature-beef-noodles")

    result = CatalogService(repository).validate_required_options(
        dish.id,
        {"spice_level": ["hot"], "portion_size": ["large"]},
    )

    assert result["total_price"] == "15.00"
