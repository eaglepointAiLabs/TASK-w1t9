from __future__ import annotations

from flask import current_app, g, jsonify, make_response, redirect, render_template, request, url_for

from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import AuthService
from app.services.errors import AppError
from app.controllers.ui_helpers import attach_feedback


def _cookie_kwargs(httponly: bool) -> dict:
    return {
        "httponly": httponly,
        "samesite": current_app.config["SESSION_COOKIE_SAMESITE"],
        "secure": current_app.config["SESSION_COOKIE_SECURE"],
    }


def render_login_page():
    if g.current_user is not None:
        return redirect(url_for("pages.render_home"))
    auth_service = AuthService(AuthRepository())
    csrf_token = auth_service.issue_csrf_token(g.client_id)
    response = make_response(render_template("auth/login.html", csrf_token=csrf_token))
    response.set_cookie("client_id", g.client_id, **_cookie_kwargs(httponly=True))
    response.set_cookie("csrf_token", csrf_token, **_cookie_kwargs(httponly=False))
    return response


def login():
    auth_service = AuthService(AuthRepository())
    payload = request.get_json(silent=True) or request.form
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    user, session = auth_service.login(
        username=username,
        password=password,
        ip_address=request.remote_addr,
        session_ttl_hours=current_app.config["SESSION_TTL_HOURS"],
        lockout_window_minutes=current_app.config["LOCKOUT_WINDOW_MINUTES"],
        lockout_max_attempts=current_app.config["LOCKOUT_MAX_ATTEMPTS"],
    )
    roles = AuthRepository().get_roles_by_user_id(user.id)
    csrf_token = auth_service.issue_csrf_token(
        client_id=g.client_id,
        session_id=session.id,
        ttl_hours=current_app.config["CSRF_TTL_HOURS"],
    )
    wants_json = request.is_json or request.headers.get("HX-Request") == "true"
    if wants_json:
        response = jsonify(
            {
                "code": "ok",
                "message": "Login successful.",
                "data": {"username": user.username, "roles": roles},
            }
        )
        response.headers["X-CSRF-Token"] = csrf_token
        if request.headers.get("HX-Request") == "true":
            response.headers["X-Redirect-Location"] = url_for("pages.render_home")
            response.headers["X-Toast-Message"] = "Signed in successfully."
            response.headers["X-Toast-Tone"] = "success"
    else:
        response = make_response(redirect(url_for("pages.render_home")))
    response.set_cookie(
        current_app.config["SESSION_COOKIE_NAME"],
        session.session_token,
        **_cookie_kwargs(httponly=True),
    )
    response.set_cookie("client_id", g.client_id, **_cookie_kwargs(httponly=True))
    response.set_cookie("csrf_token", csrf_token, **_cookie_kwargs(httponly=False))
    return response


def logout():
    auth_service = AuthService(AuthRepository())
    auth_service.logout(g.current_session)
    csrf_token = auth_service.issue_csrf_token(g.client_id)
    wants_json = request.is_json or request.headers.get("HX-Request") == "true"
    if wants_json:
        response = jsonify({"code": "ok", "message": "Logout successful.", "data": {}})
        response.headers["X-CSRF-Token"] = csrf_token
        if request.headers.get("HX-Request") == "true":
            response.headers["X-Redirect-Location"] = url_for("auth.render_login_page")
            response.headers["X-Toast-Message"] = "Signed out."
            response.headers["X-Toast-Tone"] = "success"
    else:
        response = make_response(redirect(url_for("auth.render_login_page")))
    response.delete_cookie(current_app.config["SESSION_COOKIE_NAME"])
    response.set_cookie("client_id", g.client_id, **_cookie_kwargs(httponly=True))
    response.set_cookie("csrf_token", csrf_token, **_cookie_kwargs(httponly=False))
    return response


def me():
    if g.current_user is None:
        raise AppError("authentication_required", "Authentication is required.", 401)

    return jsonify(
        {
            "code": "ok",
            "message": "Current user fetched.",
            "data": {
                "authenticated": True,
                "username": g.current_user.username,
                "roles": g.current_roles,
            },
        }
    )


def issue_nonce():
    if g.current_session is None:
        raise AppError("authentication_required", "Authentication is required.", 401)
    payload = request.get_json(silent=True) or request.form
    purpose = (payload.get("purpose") or "").strip()
    if not purpose:
        raise AppError("validation_error", "purpose is required.", 400)
    nonce = AuthService(AuthRepository()).issue_nonce(
        session_id=g.current_session.id,
        purpose=purpose,
        ttl_minutes=current_app.config["NONCE_TTL_MINUTES"],
    )
    return jsonify({"code": "ok", "message": "Nonce issued.", "data": {"purpose": purpose, "nonce": nonce}})


def render_home():
    if g.current_user is None:
        return redirect(url_for("auth.render_login_page"))
    return render_template("home/dashboard.html", user=g.current_user, roles=g.current_roles)
