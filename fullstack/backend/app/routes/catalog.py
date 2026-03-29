from flask import Blueprint

from app.controllers.catalog_controller import (
    create_dish,
    get_dish,
    list_dishes,
    manager_dishes_page,
    menu_page,
    publish_dish,
    serve_upload,
    update_dish,
    upload_dish_image,
    validate_dish_selection,
)


catalog_bp = Blueprint("catalog", __name__)

catalog_bp.get("/menu")(menu_page)
catalog_bp.get("/manager/dishes")(manager_dishes_page)
catalog_bp.get("/api/dishes")(list_dishes)
catalog_bp.get("/api/dishes/<dish_id>")(get_dish)
catalog_bp.post("/api/dishes/<dish_id>/selection-check")(validate_dish_selection)
catalog_bp.post("/api/manager/dishes")(create_dish)
catalog_bp.patch("/api/manager/dishes/<dish_id>")(update_dish)
catalog_bp.post("/api/manager/dishes/<dish_id>/publish")(publish_dish)
catalog_bp.post("/api/manager/dishes/<dish_id>/images")(upload_dish_image)
catalog_bp.get("/uploads/<path:relative_path>")(serve_upload)
