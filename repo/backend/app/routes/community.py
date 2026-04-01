from flask import Blueprint

from app.controllers.community_controller import (
    block_user,
    community_page,
    create_comment,
    create_report,
    toggle_favorite,
    toggle_like,
    unblock_user,
)


community_bp = Blueprint("community", __name__)

community_bp.get("/community")(community_page)
community_bp.post("/api/community/likes/toggle")(toggle_like)
community_bp.post("/api/community/favorites/toggle")(toggle_favorite)
community_bp.post("/api/community/comments")(create_comment)
community_bp.post("/api/community/reports")(create_report)
community_bp.post("/api/community/blocks")(block_user)
community_bp.delete("/api/community/blocks/<blocked_user_id>")(unblock_user)
