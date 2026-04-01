from __future__ import annotations

from flask import g, jsonify, render_template, request

from app.controllers.ui_helpers import attach_feedback, redirect_anonymous_to_login
from app.repositories.community_repository import CommunityRepository
from app.services.errors import AppError
from app.services.community_service import CommunityService
from app.services.time_utils import serialize_utc_datetime


def _service():
    return CommunityService(CommunityRepository())


def _serialize_comment(comment):
    return {
        "id": comment.id,
        "author_user_id": comment.author_user_id,
        "body": comment.body,
        "created_at": serialize_utc_datetime(comment.created_at),
    }


def _build_post_view(post, current_user_id: str):
    repository = CommunityRepository()
    return {
        "id": post.id,
        "title": post.title,
        "body": post.body,
        "author_user_id": post.author_user_id,
        "like_count": repository.count_likes("post", post.id),
        "favorite_count": repository.count_favorites("post", post.id),
        "liked": repository.get_like(current_user_id, "post", post.id) is not None,
        "favorited": repository.get_favorite(current_user_id, "post", post.id) is not None,
        "blocked": repository.get_block(current_user_id, post.author_user_id) is not None,
        "comments": [_serialize_comment(comment) for comment in repository.list_comments("post", post.id)],
    }


def _render_post_card(post_id: str):
    repository = CommunityRepository()
    post = repository.get_post(post_id)
    if post is None:
        raise AppError("not_found", "Post not found.", 404)
    return render_template("partials/community_post.html", post=_build_post_view(post, g.current_user.id))


def community_page():
    redirect_response = redirect_anonymous_to_login()
    if redirect_response is not None:
        return redirect_response
    service = _service()
    posts = service.list_posts()
    post_cards = [_build_post_view(post, g.current_user.id) for post in posts]
    return render_template("community/index.html", posts=post_cards)


def toggle_like():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    payload = request.get_json(silent=True) or request.form
    result = _service().toggle_like(g.current_user.id, payload)
    if request.headers.get("HX-Request") == "true" and (payload.get("target_type") or "").strip() == "post":
        return attach_feedback(_render_post_card((payload.get("target_id") or "").strip()), "Like updated.")
    return jsonify({"code": "ok", "message": "Like toggled.", "data": result})


def toggle_favorite():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    payload = request.get_json(silent=True) or request.form
    result = _service().toggle_favorite(g.current_user.id, payload)
    if request.headers.get("HX-Request") == "true" and (payload.get("target_type") or "").strip() == "post":
        return attach_feedback(_render_post_card((payload.get("target_id") or "").strip()), "Favorite updated.")
    return jsonify({"code": "ok", "message": "Favorite toggled.", "data": result})


def create_comment():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    payload = request.get_json(silent=True) or request.form
    comment = _service().create_comment(g.current_user, payload)
    if request.headers.get("HX-Request") == "true" and (payload.get("target_type") or "").strip() == "post":
        return attach_feedback((_render_post_card((payload.get("target_id") or "").strip()), 201), "Comment posted.")
    return jsonify(
        {
            "code": "ok",
            "message": "Comment created.",
            "data": {"id": comment.id, "target_type": comment.target_type, "target_id": comment.target_id, "body": comment.body},
        }
    ), 201


def create_report():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    payload = request.get_json(silent=True) or request.form
    report = _service().create_report(g.current_user, payload)
    if request.headers.get("HX-Request") == "true" and (payload.get("target_type") or "").strip() == "post":
        return attach_feedback((_render_post_card((payload.get("target_id") or "").strip()), 201), "Report submitted.", tone="warning")
    return jsonify({"code": "ok", "message": "Report submitted.", "data": {"id": report.id, "status": report.status}}), 201


def block_user():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    payload = request.get_json(silent=True) or request.form
    result = _service().block_user(g.current_user.id, (payload.get("blocked_user_id") or "").strip())
    post_id = (payload.get("post_id") or "").strip()
    if request.headers.get("HX-Request") == "true" and post_id:
        return attach_feedback((_render_post_card(post_id), 201), "User blocked.", tone="warning")
    return jsonify({"code": "ok", "message": "User blocked.", "data": result}), 201


def unblock_user(blocked_user_id: str):
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    result = _service().unblock_user(g.current_user.id, blocked_user_id)
    post_id = (request.get_json(silent=True) or request.form).get("post_id", "").strip() if request.method == "DELETE" else ""
    if request.headers.get("HX-Request") == "true" and post_id:
        return attach_feedback(_render_post_card(post_id), "User unblocked.")
    return jsonify({"code": "ok", "message": "User unblocked.", "data": result})
