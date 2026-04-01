from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Dish,
    DishAvailabilityWindow,
    DishCategory,
    DishImage,
    DishOption,
    DishOptionRule,
    DishOptionValue,
    DishTag,
    DishTagMap,
)


class CatalogRepository:
    def _dish_load_options(self):
        return (
            joinedload(Dish.category),
            joinedload(Dish.tag_links).joinedload(DishTagMap.tag),
            joinedload(Dish.availability_windows),
            joinedload(Dish.options).joinedload(DishOption.values),
            joinedload(Dish.options).joinedload(DishOption.rules),
            joinedload(Dish.images),
        )

    def get_category_by_slug(self, slug: str) -> DishCategory | None:
        stmt = select(DishCategory).where(DishCategory.slug == slug)
        return db.session.scalar(stmt)

    def get_or_create_category(self, name: str, slug: str) -> DishCategory:
        category = self.get_category_by_slug(slug)
        if category is None:
            category = DishCategory(name=name, slug=slug)
            db.session.add(category)
            db.session.flush()
        return category

    def get_tag_by_slug(self, slug: str) -> DishTag | None:
        stmt = select(DishTag).where(DishTag.slug == slug)
        return db.session.scalar(stmt)

    def get_or_create_tag(self, name: str, slug: str) -> DishTag:
        tag = self.get_tag_by_slug(slug)
        if tag is None:
            tag = DishTag(name=name, slug=slug)
            db.session.add(tag)
            db.session.flush()
        return tag

    def create_dish(self, **kwargs) -> Dish:
        dish = Dish(**kwargs)
        db.session.add(dish)
        db.session.flush()
        return dish

    def get_dish(self, dish_id: str) -> Dish | None:
        stmt = (
            select(Dish)
            .options(*self._dish_load_options())
            .where(Dish.id == dish_id)
        )
        return db.session.execute(stmt).unique().scalar_one_or_none()

    def get_dishes_by_ids(self, dish_ids: list[str]) -> list[Dish]:
        if not dish_ids:
            return []
        stmt = select(Dish).options(*self._dish_load_options()).where(Dish.id.in_(dish_ids))
        dishes = {dish.id: dish for dish in db.session.execute(stmt).unique().scalars()}
        return [dishes[dish_id] for dish_id in dish_ids if dish_id in dishes]

    def get_dish_by_slug(self, slug: str) -> Dish | None:
        stmt = select(Dish).where(Dish.slug == slug)
        return db.session.scalar(stmt)

    def list_categories(self) -> list[DishCategory]:
        stmt = select(DishCategory).order_by(DishCategory.sort_order.asc(), DishCategory.name.asc())
        return list(db.session.scalars(stmt))

    def list_tags(self) -> list[DishTag]:
        stmt = select(DishTag).order_by(DishTag.name.asc())
        return list(db.session.scalars(stmt))

    def list_dishes(
        self,
        category_slug: str | None = None,
        tag_slugs: list[str] | None = None,
        include_sold_out: bool = False,
        available_at: datetime | None = None,
        published_only: bool = True,
    ) -> list[Dish]:
        stmt = (
            select(Dish)
            .options(*self._dish_load_options())
            .where(Dish.archived_at.is_(None))
            .order_by(Dish.sort_order.asc(), Dish.name.asc())
        )

        if published_only:
            stmt = stmt.where(Dish.is_published.is_(True))
        if not include_sold_out:
            stmt = stmt.where(Dish.is_sold_out.is_(False))
        if category_slug:
            stmt = stmt.join(DishCategory, Dish.category_id == DishCategory.id).where(DishCategory.slug == category_slug)
        if tag_slugs:
            stmt = (
                stmt.join(DishTagMap, DishTagMap.dish_id == Dish.id)
                .join(DishTag, DishTagMap.tag_id == DishTag.id)
                .where(DishTag.slug.in_(tag_slugs))
            )
        if available_at is not None:
            stmt = stmt.join(
                DishAvailabilityWindow,
                and_(
                    DishAvailabilityWindow.dish_id == Dish.id,
                    DishAvailabilityWindow.is_enabled.is_(True),
                ),
                isouter=True,
            )

        dishes = list(db.session.execute(stmt).unique().scalars())
        if available_at is None:
            return dishes

        weekday = available_at.weekday()
        current_time = available_at.time()
        result = []
        for dish in dishes:
            windows = [window for window in dish.availability_windows if window.is_enabled]
            if not windows:
                result.append(dish)
                continue
            if any(
                window.day_of_week == weekday and window.start_time <= current_time < window.end_time
                for window in windows
            ):
                result.append(dish)
        return result

    def replace_dish_tags(self, dish: Dish, tags: list[DishTag]) -> None:
        dish.tag_links.clear()
        for tag in tags:
            dish.tag_links.append(DishTagMap(tag_id=tag.id))
        db.session.flush()

    def replace_availability_windows(self, dish: Dish, windows: list[dict]) -> None:
        dish.availability_windows.clear()
        for window in windows:
            dish.availability_windows.append(DishAvailabilityWindow(**window))
        db.session.flush()

    def replace_options(self, dish: Dish, options: list[dict]) -> None:
        dish.options.clear()
        for option_payload in options:
            option = DishOption(
                name=option_payload["name"],
                code=option_payload["code"],
                display_type=option_payload.get("display_type", "single_select"),
                sort_order=int(option_payload.get("sort_order", 0)),
            )
            for value_payload in option_payload.get("values", []):
                option.values.append(
                    DishOptionValue(
                        label=value_payload["label"],
                        value_code=value_payload["value_code"],
                        price_delta=value_payload["price_delta"],
                        is_available=bool(value_payload.get("is_available", True)),
                        sort_order=int(value_payload.get("sort_order", 0)),
                    )
                )
            for rule_payload in option_payload.get("rules", []):
                option.rules.append(
                    DishOptionRule(
                        rule_type=rule_payload["rule_type"],
                        is_required=bool(rule_payload.get("is_required", False)),
                        min_select=int(rule_payload.get("min_select", 0)),
                        max_select=int(rule_payload.get("max_select", 1)),
                    )
                )
            dish.options.append(option)
        db.session.flush()

    def add_image(self, dish_id: str, **kwargs) -> DishImage:
        image = DishImage(dish_id=dish_id, **kwargs)
        db.session.add(image)
        db.session.flush()
        return image

    def set_primary_image(self, dish_id: str, image_id: str) -> None:
        stmt = select(DishImage).where(DishImage.dish_id == dish_id)
        for image in db.session.scalars(stmt):
            image.is_primary = image.id == image_id
            db.session.add(image)
        db.session.flush()
