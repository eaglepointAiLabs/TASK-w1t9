from __future__ import annotations

from collections import defaultdict

from flask import current_app, g, jsonify, render_template, request, send_from_directory

from app.controllers.ui_helpers import attach_feedback, redirect_anonymous_to_login
from app.repositories.catalog_repository import CatalogRepository
from app.services.catalog_service import CatalogService
from app.services.rbac_service import RBACService


def _serialize_dish(dish):
    return {
        "id": dish.id,
        "name": dish.name,
        "slug": dish.slug,
        "description": dish.description,
        "base_price": f"{dish.base_price:.2f}",
        "category": dish.category.name if dish.category else None,
        "category_slug": dish.category.slug if dish.category else None,
        "tags": [link.tag.name for link in dish.tag_links],
        "is_published": dish.is_published,
        "is_sold_out": dish.is_sold_out,
        "stock_quantity": dish.stock_quantity,
        "sort_order": dish.sort_order,
        "images": [
            {
                "id": image.id,
                "url": f"/uploads/{image.stored_path.replace('\\', '/')}",
                "mime_type": image.mime_type,
                "size_bytes": image.size_bytes,
                "is_primary": image.is_primary,
            }
            for image in dish.images
        ],
        "options": [
            {
                "id": option.id,
                "name": option.name,
                "code": option.code,
                "display_type": option.display_type,
                "rules": [
                    {
                        "rule_type": rule.rule_type,
                        "is_required": rule.is_required,
                        "min_select": rule.min_select,
                        "max_select": rule.max_select,
                    }
                    for rule in option.rules
                ],
                "values": [
                    {
                        "id": value.id,
                        "label": value.label,
                        "value_code": value.value_code,
                        "price_delta": f"{value.price_delta:.2f}",
                        "is_available": value.is_available,
                    }
                    for value in option.values
                ],
            }
            for option in dish.options
        ],
    }


def menu_page():
    repository = CatalogRepository()
    filters = {
        "category": request.args.get("category"),
        "tags": request.args.getlist("tag"),
        "available_at": request.args.get("available_at"),
        "include_sold_out": request.args.get("include_sold_out") == "1",
    }
    dishes = CatalogService(repository).list_dishes(
        category_slug=filters["category"],
        tag_slugs=filters["tags"],
        include_sold_out=filters["include_sold_out"],
        available_at=filters["available_at"],
    )
    return render_template(
        "menu/index.html",
        dishes=dishes,
        categories=repository.list_categories(),
        tags=repository.list_tags(),
        filters=filters,
    )


def manager_dishes_page():
    redirect_response = redirect_anonymous_to_login()
    if redirect_response is not None:
        return redirect_response
    RBACService().require_roles(g.current_roles, ["Store Manager"])
    repository = CatalogRepository()
    dishes = CatalogService(repository).list_dishes(published_only=False, include_sold_out=True)
    return render_template("manager/dishes.html", dishes=dishes, categories=repository.list_categories())


def list_dishes():
    repository = CatalogRepository()
    filters = {
        "category": request.args.get("category"),
        "tags": request.args.getlist("tag"),
        "available_at": request.args.get("available_at"),
        "include_sold_out": request.args.get("include_sold_out") == "1",
    }
    published_only = "Store Manager" not in g.current_roles or request.args.get("scope") != "manager"
    dishes = CatalogService(repository).list_dishes(
        category_slug=filters["category"],
        tag_slugs=filters["tags"],
        include_sold_out=filters["include_sold_out"],
        available_at=filters["available_at"],
        published_only=published_only,
    )
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/dish_list.html", dishes=dishes)
    return jsonify({"code": "ok", "message": "Dishes fetched.", "data": [_serialize_dish(dish) for dish in dishes]})


def get_dish(dish_id: str):
    dish = CatalogRepository().get_dish(dish_id)
    if dish is None:
        return jsonify({"code": "not_found", "message": "Dish not found.", "details": {}}), 404
    if (not dish.is_published or dish.archived_at is not None) and "Store Manager" not in g.current_roles:
        return jsonify({"code": "not_found", "message": "Dish not found.", "details": {}}), 404
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/dish_detail.html", dish=dish)
    return jsonify({"code": "ok", "message": "Dish fetched.", "data": _serialize_dish(dish)})


def create_dish():
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
    payload = _inflate_payload(payload)
    dish = CatalogService(CatalogRepository()).create_dish(payload, g.current_roles)
    if request.headers.get("HX-Request") == "true":
        return attach_feedback((render_template("partials/manager_dish_row.html", dish=dish), 201), "Dish created.")
    return jsonify({"code": "ok", "message": "Dish created.", "data": _serialize_dish(dish)}), 201


def update_dish(dish_id: str):
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
    payload = _inflate_payload(payload)
    dish = CatalogService(CatalogRepository()).update_dish(dish_id, payload, g.current_roles)
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/manager_dish_row.html", dish=dish)
    return jsonify({"code": "ok", "message": "Dish updated.", "data": _serialize_dish(dish)})


def publish_dish(dish_id: str):
    payload = request.get_json(silent=True) or request.form
    publish = str(payload.get("publish", "true")).lower() == "true"
    dish = CatalogService(CatalogRepository()).publish_dish(dish_id, publish, g.current_roles)
    if request.headers.get("HX-Request") == "true":
        return attach_feedback(render_template("partials/manager_dish_row.html", dish=dish), "Publish state updated.")
    return jsonify({"code": "ok", "message": "Publish state updated.", "data": _serialize_dish(dish)})


def upload_dish_image(dish_id: str):
    image = request.files.get("image")
    dish_image = CatalogService(CatalogRepository()).upload_image(
        dish_id=dish_id,
        image=image,
        current_roles=g.current_roles,
        upload_root=current_app.config["UPLOAD_DIR"],
    )
    dish = CatalogRepository().get_dish(dish_id)
    if request.headers.get("HX-Request") == "true":
        return attach_feedback(
            render_template("partials/image_gallery.html", dish=dish, upload_message="Image uploaded."),
            "Image uploaded.",
        )
    return jsonify(
        {
            "code": "ok",
            "message": "Image uploaded.",
            "data": {
                "id": dish_image.id,
                "url": f"/uploads/{dish_image.stored_path.replace('\\', '/')}",
                "mime_type": dish_image.mime_type,
                "size_bytes": dish_image.size_bytes,
            },
        }
    )


def validate_dish_selection(dish_id: str):
    payload = request.get_json(silent=True) or request.form
    grouped = defaultdict(list)
    for key in payload:
        if key.startswith("option_"):
            grouped[key.removeprefix("option_")].extend(payload.getlist(key))
    result = CatalogService(CatalogRepository()).validate_required_options(dish_id, grouped)
    if request.headers.get("HX-Request") == "true":
        dish = CatalogRepository().get_dish(dish_id)
        return attach_feedback(render_template("partials/selection_status.html", dish=dish, selection=result), "Selections look good.")
    return jsonify({"code": "ok", "message": "Selections valid.", "data": result})


def serve_upload(relative_path: str):
    root = current_app.config["UPLOAD_DIR"].parent
    return send_from_directory(root, relative_path)


def _inflate_payload(payload: dict) -> dict:
    if "tags" in payload and isinstance(payload["tags"], str):
        payload["tags"] = [tag.strip() for tag in payload["tags"].split(",") if tag.strip()]
    if "availability_windows" in payload and isinstance(payload["availability_windows"], str):
        import json

        payload["availability_windows"] = json.loads(payload["availability_windows"] or "[]")
    if "options" in payload and isinstance(payload["options"], str):
        import json

        payload["options"] = json.loads(payload["options"] or "[]")
    return payload
