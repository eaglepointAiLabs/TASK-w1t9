from flask import Blueprint

from app.controllers.moderation_controller import admin_page, change_role, decide_item, get_history, get_queue, moderation_page


moderation_bp = Blueprint("moderation", __name__)

moderation_bp.get("/moderation")(moderation_page)
moderation_bp.get("/admin/roles")(admin_page)
moderation_bp.get("/api/moderation/queue")(get_queue)
moderation_bp.post("/api/moderation/items/<item_id>/decision")(decide_item)
moderation_bp.get("/api/moderation/items/<item_id>/history")(get_history)
moderation_bp.post("/api/admin/roles/change")(change_role)
