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


def test_list_dishes_returns_published_only_by_default(app):
    service = CatalogService(CatalogRepository())
    dishes = service.list_dishes()

    for dish in dishes:
        assert dish.is_published is True


def test_list_dishes_excludes_sold_out_by_default(app):
    service = CatalogService(CatalogRepository())
    dishes = service.list_dishes(include_sold_out=False)

    for dish in dishes:
        assert dish.is_sold_out is False


def test_list_dishes_filters_by_category(app):
    service = CatalogService(CatalogRepository())
    dishes = service.list_dishes(category_slug="noodles")

    assert len(dishes) > 0
    for dish in dishes:
        assert dish.category.slug == "noodles"


def test_create_dish_requires_store_manager_role(app):
    service = CatalogService(CatalogRepository())

    with pytest.raises(AppError) as exc:
        service.create_dish(
            {
                "name": "New Dish",
                "base_price": "10.00",
                "category_name": "Bowls",
                "options": [],
                "availability_windows": [],
            },
            ["Customer"],
        )
    assert exc.value.code == "forbidden"


def test_create_dish_succeeds_for_store_manager(app):
    service = CatalogService(CatalogRepository())
    dish = service.create_dish(
        {
            "name": "Unit Test Dish",
            "base_price": "12.50",
            "category_name": "Bowls",
            "tags": ["new", "test"],
            "options": [
                {
                    "name": "Size",
                    "values": [{"label": "Regular", "price_delta": "0.00"}, {"label": "Large", "price_delta": "2.00"}],
                    "rules": [{"rule_type": "single_select_required", "is_required": True, "min_select": 1, "max_select": 1}],
                }
            ],
            "availability_windows": [],
        },
        ["Store Manager"],
    )

    assert dish.name == "Unit Test Dish"
    assert str(dish.base_price) == "12.50"
    assert len(dish.options) == 1
    assert len(dish.options[0].values) == 2


def test_publish_dish_toggles_state(app):
    repository = CatalogRepository()
    service = CatalogService(repository)
    dish = repository.get_dish_by_slug("citrus-tofu-bowl")

    updated = service.publish_dish(dish.id, False, ["Store Manager"])
    assert updated.is_published is False

    restored = service.publish_dish(dish.id, True, ["Store Manager"])
    assert restored.is_published is True


def test_publish_dish_rejects_nonexistent_id(app):
    service = CatalogService(CatalogRepository())

    with pytest.raises(AppError) as exc:
        service.publish_dish("nonexistent-id", True, ["Store Manager"])
    assert exc.value.code == "not_found"


def test_validate_required_options_rejects_nonexistent_dish(app):
    service = CatalogService(CatalogRepository())

    with pytest.raises(AppError) as exc:
        service.validate_required_options("nonexistent-dish-id", {})
    assert exc.value.code == "not_found"


def test_bulk_update_rejects_empty_dish_ids(app):
    service = CatalogService(CatalogRepository())

    with pytest.raises(AppError) as exc:
        service.queue_bulk_update([], True, None, "operator-id", ["Store Manager"])
    assert exc.value.code == "validation_error"


def test_bulk_update_rejects_no_changes(app):
    service = CatalogService(CatalogRepository())

    with pytest.raises(AppError) as exc:
        service.queue_bulk_update(["some-id"], None, None, "operator-id", ["Store Manager"])
    assert exc.value.code == "validation_error"
