from __future__ import annotations

from datetime import time
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import structlog
from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Dish
from app.repositories.catalog_repository import CatalogRepository
from app.services.ops_service import MenuCache
from app.services.catalog_validation import (
    normalize_slug,
    parse_bool,
    parse_iso_datetime,
    parse_price,
    validate_dish_payload,
    validate_image_upload,
)
from app.services.errors import AppError
from app.services.rbac_service import RBACService
from app.services.time_utils import utc_now_naive


logger = structlog.get_logger(__name__)


class CatalogService:
    def __init__(self, repository: CatalogRepository) -> None:
        self.repository = repository
        self.rbac = RBACService()

    def list_dishes(
        self,
        category_slug: str | None = None,
        tag_slugs: list[str] | None = None,
        include_sold_out: bool = False,
        available_at: str | None = None,
        published_only: bool = True,
    ) -> list[Dish]:
        cache_key = f"{category_slug}|{','.join(sorted(tag_slugs or []))}|{include_sold_out}|{available_at}|{published_only}"
        cached_ids = MenuCache.get(cache_key, current_app.config["MENU_CACHE_TTL_SECONDS"])
        if cached_ids is not None:
            return self.repository.get_dishes_by_ids(cached_ids)
        dishes = self.repository.list_dishes(
            category_slug=category_slug,
            tag_slugs=tag_slugs,
            include_sold_out=include_sold_out,
            available_at=parse_iso_datetime(available_at),
            published_only=published_only,
        )
        MenuCache.put(cache_key, [dish.id for dish in dishes])
        return dishes

    def create_dish(self, payload: dict, current_roles: list[str]) -> Dish:
        self.rbac.require_roles(current_roles, ["Store Manager"])
        validate_dish_payload(payload)
        dish = self._upsert_dish(None, payload)
        MenuCache.clear()
        db.session.commit()
        logger.info("catalog.dish_created", dish_id=dish.id, name=dish.name)
        return dish

    def update_dish(self, dish_id: str, payload: dict, current_roles: list[str]) -> Dish:
        self.rbac.require_roles(current_roles, ["Store Manager"])
        validate_dish_payload(payload)
        dish = self.repository.get_dish(dish_id)
        if dish is None:
            raise AppError("not_found", "Dish not found.", 404)
        dish = self._upsert_dish(dish, payload)
        MenuCache.clear()
        db.session.commit()
        logger.info("catalog.dish_updated", dish_id=dish.id, name=dish.name)
        return dish

    def publish_dish(self, dish_id: str, publish: bool, current_roles: list[str]) -> Dish:
        self.rbac.require_roles(current_roles, ["Store Manager"])
        dish = self.repository.get_dish(dish_id)
        if dish is None:
            raise AppError("not_found", "Dish not found.", 404)
        dish.is_published = publish
        db.session.add(dish)
        MenuCache.clear()
        db.session.commit()
        logger.info("catalog.dish_publish_changed", dish_id=dish.id, publish=publish)
        return dish

    def upload_image(
        self,
        dish_id: str,
        image: FileStorage | None,
        current_roles: list[str],
        upload_root: Path,
    ):
        self.rbac.require_roles(current_roles, ["Store Manager"])
        dish = self.repository.get_dish(dish_id)
        if dish is None:
            raise AppError("not_found", "Dish not found.", 404)
        if image is None or image.filename == "":
            raise AppError("validation_error", "Image file is required.", 400)

        content = image.stream.read()
        size_bytes = len(content)
        image.stream.seek(0)
        validate_image_upload(image.mimetype, size_bytes)

        suffix = ".jpg" if image.mimetype == "image/jpeg" else ".png"
        safe_name = secure_filename(Path(image.filename).stem) or "dish"
        filename = f"{safe_name}-{uuid4().hex}{suffix}"
        destination_dir = upload_root / dish_id
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_path = destination_dir / filename
        with destination_path.open("wb") as output:
            output.write(content)

        dish_image = self.repository.add_image(
            dish_id=dish.id,
            filename=image.filename,
            stored_path=str(destination_path.relative_to(upload_root.parent)),
            mime_type=image.mimetype,
            size_bytes=size_bytes,
            alt_text=dish.name,
            is_primary=len(dish.images) == 0,
        )
        if dish_image.is_primary:
            self.repository.set_primary_image(dish.id, dish_image.id)
        MenuCache.clear()
        db.session.commit()
        logger.info("catalog.image_uploaded", dish_id=dish.id, image_id=dish_image.id, size_bytes=size_bytes)
        return dish_image

    def validate_required_options(self, dish_id: str, selected_values: dict[str, list[str] | str]) -> dict:
        dish = self.repository.get_dish(dish_id)
        if dish is None:
            raise AppError("not_found", "Dish not found.", 404)

        errors = []
        running_total = Decimal(dish.base_price)
        normalized = {
            key: value if isinstance(value, list) else [value]
            for key, value in selected_values.items()
            if value not in (None, "", [])
        }

        for option in dish.options:
            selected_codes = normalized.get(option.code, [])
            available_codes = {value.value_code: value for value in option.values if value.is_available}
            for rule in option.rules:
                if rule.is_required and len(selected_codes) < rule.min_select:
                    errors.append(f"{option.name} is required.")
                if len(selected_codes) > rule.max_select:
                    errors.append(f"{option.name} exceeds the allowed number of selections.")
            for code in selected_codes:
                if code not in available_codes:
                    errors.append(f"{option.name} contains an invalid selection.")
                else:
                    running_total += Decimal(available_codes[code].price_delta)

        if errors:
            raise AppError(
                "required_options_missing",
                "Required option selections are incomplete.",
                400,
                {"errors": errors},
            )

        return {"dish_id": dish.id, "dish_name": dish.name, "total_price": f"{running_total:.2f}"}

    def _upsert_dish(self, dish: Dish | None, payload: dict) -> Dish:
        category_name = (payload.get("category_name") or "").strip()
        category_slug = normalize_slug(payload.get("category_slug") or category_name) if category_name else None
        category = None
        if category_name and category_slug:
            category = self.repository.get_or_create_category(category_name, category_slug)

        if dish is None:
            dish = self.repository.create_dish(
                category_id=category.id if category else None,
                name=payload["name"].strip(),
                slug=normalize_slug(payload.get("slug") or payload["name"]),
                description=(payload.get("description") or "").strip(),
                base_price=parse_price(payload.get("base_price"), "base_price"),
                is_published=parse_bool(payload.get("is_published", False)),
                is_sold_out=parse_bool(payload.get("is_sold_out", False)),
                stock_quantity=int(payload.get("stock_quantity", 0)),
                sort_order=int(payload.get("sort_order", 0)),
            )
        else:
            dish.category_id = category.id if category else None
            dish.name = payload["name"].strip()
            dish.slug = normalize_slug(payload.get("slug") or payload["name"])
            dish.description = (payload.get("description") or "").strip()
            dish.base_price = parse_price(payload.get("base_price"), "base_price")
            dish.is_sold_out = parse_bool(payload.get("is_sold_out", False))
            dish.stock_quantity = int(payload.get("stock_quantity", dish.stock_quantity))
            dish.sort_order = int(payload.get("sort_order", 0))
            if "archived" in payload:
                dish.archived_at = utc_now_naive() if parse_bool(payload.get("archived")) else None
            db.session.add(dish)
            db.session.flush()

        tags = []
        for tag_name in payload.get("tags", []):
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            tags.append(self.repository.get_or_create_tag(tag_name, normalize_slug(tag_name)))
        self.repository.replace_dish_tags(dish, tags)

        windows = []
        for window in payload.get("availability_windows", []):
            windows.append(
                {
                    "day_of_week": int(window["day_of_week"]),
                    "start_time": time.fromisoformat(window["start_time"]),
                    "end_time": time.fromisoformat(window["end_time"]),
                    "is_enabled": bool(window.get("is_enabled", True)),
                }
            )
        self.repository.replace_availability_windows(dish, windows)

        options = []
        for option in payload.get("options", []):
            options.append(
                {
                    "name": option["name"].strip(),
                    "code": normalize_slug(option.get("code") or option["name"]).replace("-", "_"),
                    "display_type": option.get("display_type", "single_select"),
                    "sort_order": int(option.get("sort_order", 0)),
                    "values": [
                        {
                            "label": item["label"].strip(),
                            "value_code": normalize_slug(item.get("value_code") or item["label"]).replace("-", "_"),
                            "price_delta": parse_price(item.get("price_delta", 0), "price_delta"),
                            "is_available": bool(item.get("is_available", True)),
                            "sort_order": int(item.get("sort_order", 0)),
                        }
                        for item in option.get("values", [])
                    ],
                    "rules": [
                        {
                            "rule_type": rule["rule_type"],
                            "is_required": bool(rule.get("is_required", False)),
                            "min_select": int(rule.get("min_select", 0)),
                            "max_select": int(rule.get("max_select", 1)),
                        }
                        for rule in option.get("rules", [])
                    ],
                }
            )
        self.repository.replace_options(dish, options)
        return dish
