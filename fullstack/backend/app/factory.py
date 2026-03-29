from __future__ import annotations

import os
from pathlib import Path
from secrets import token_urlsafe

import structlog
from flask import Flask, g, jsonify, make_response, render_template, request, url_for

from app.config import CONFIG_BY_NAME
from app.extensions import bcrypt, db, migrate
from app.logging import bind_request_context, configure_logging
from app.repositories.auth_repository import AuthRepository
from app.routes import auth_bp, catalog_bp, orders_bp, pages_bp, payments_bp, reconciliation_bp, refunds_bp, community_bp, moderation_bp, ops_bp
from app.services.auth_service import AuthService
from app.services.errors import AppError, sanitize_error_details
from app.repositories.ops_repository import OpsRepository
from app.services.ops_service import OpsService


logger = structlog.get_logger(__name__)


def create_app(config_name: str | None = None) -> Flask:
    config_name = config_name or os.getenv("TABLEPAY_ENV") or os.getenv("FLASK_ENV") or "development"
    if config_name not in CONFIG_BY_NAME:
        raise RuntimeError(f"Unknown application config '{config_name}'.")
    config_class = CONFIG_BY_NAME[config_name]
    config_class.init_app()

    configure_logging()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_class)
    app.config.update(config_class.runtime_overrides())
    config_class.validate(app.config)

    db.init_app(app)
    migrate.init_app(app, db, directory=str(Path(app.root_path).parent / "migrations"))
    bcrypt.init_app(app)

    from app.cli import register_cli

    register_cli(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(reconciliation_bp)
    app.register_blueprint(refunds_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(moderation_bp)
    app.register_blueprint(ops_bp)
    app.register_blueprint(pages_bp)

    @app.before_request
    def load_identity() -> None:
        g.request_id = request.headers.get("X-Request-Id") or token_urlsafe(12)
        g.client_id = request.cookies.get("client_id") or token_urlsafe(24)
        auth_service = AuthService(AuthRepository())
        current_user, current_session, current_roles = auth_service.get_current_user(
            request.cookies.get(app.config["SESSION_COOKIE_NAME"])
        )
        g.current_user = current_user
        g.current_session = current_session
        g.current_roles = current_roles
        bind_request_context(
            request_id=g.request_id,
            actor=getattr(current_user, "username", None),
            endpoint=request.path,
        )
        ops_service = OpsService(OpsRepository())
        actor_key = getattr(current_user, "id", None) or g.client_id
        ops_service.enforce_rate_limit(actor_key)
        ops_service.before_endpoint(request.path)

        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            token = request.headers.get("X-CSRF-Token")
            if token is None:
                token = request.form.get("csrf_token")
            auth_service.validate_csrf(token=token, client_id=g.client_id)

    @app.after_request
    def apply_client_cookie(response):
        response.set_cookie(
            "client_id",
            g.client_id,
            httponly=True,
            samesite=app.config["SESSION_COOKIE_SAMESITE"],
            secure=app.config["SESSION_COOKIE_SECURE"],
        )
        response.headers["X-Request-Id"] = g.request_id
        failed = response.status_code >= 500 or response.status_code == 503
        OpsService(OpsRepository()).record_endpoint_result(request.path, failed)
        return response

    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        severity = "high" if error.status_code >= 500 else "medium" if error.status_code >= 400 else "low"
        safe_details = sanitize_error_details(error.details)
        logger.info(
            "app.error",
            code=error.code,
            message=error.message,
            details=safe_details,
            error_class=error.__class__.__name__,
            severity=severity,
            context={"request_id": g.get("request_id"), "actor": getattr(g.get("current_user"), "username", None)},
        )
        wants_json = (
            request.accept_mimetypes.best == "application/json"
            or request.path.startswith(("/auth/", "/api/"))
            or request.is_json
        )
        if wants_json:
            response = make_response(
                jsonify({"code": error.code, "message": error.message, "details": safe_details}),
                error.status_code,
            )
        else:
            response = make_response(
                render_template(
                    "errors/app_error.html",
                    error_code=error.code,
                    error_message=error.message,
                    details=safe_details,
                ),
                error.status_code,
            )
        if request.headers.get("HX-Request") == "true":
            response.headers["X-Toast-Message"] = error.message
            response.headers["X-Toast-Tone"] = "error"
            response.headers["X-Error-Code"] = error.code
            if error.status_code == 401:
                response.headers["X-Redirect-Location"] = url_for("auth.render_login_page")
        return response

    @app.errorhandler(404)
    def handle_not_found(_error):
        logger.info("app.not_found", error_class="NotFound", severity="low", context={"request_id": g.get("request_id")})
        payload = {"code": "not_found", "message": "Not found.", "details": {}}
        wants_json = (
            request.accept_mimetypes.best == "application/json"
            or request.path.startswith(("/auth/", "/api/"))
            or request.is_json
        )
        if wants_json:
            response = make_response(jsonify(payload), 404)
        else:
            response = make_response(
                render_template(
                    "errors/app_error.html",
                    error_code="not_found",
                    error_message="Not found.",
                    details={},
                ),
                404,
            )
        if request.headers.get("HX-Request") == "true":
            response.headers["X-Toast-Message"] = payload["message"]
            response.headers["X-Toast-Tone"] = "error"
            response.headers["X-Error-Code"] = payload["code"]
        return response

    @app.errorhandler(405)
    def handle_method_not_allowed(_error):
        payload = {"code": "method_not_allowed", "message": "Method not allowed.", "details": {}}
        wants_json = (
            request.accept_mimetypes.best == "application/json"
            or request.path.startswith(("/auth/", "/api/"))
            or request.is_json
        )
        if wants_json:
            response = make_response(jsonify(payload), 405)
        else:
            response = make_response(
                render_template(
                    "errors/app_error.html",
                    error_code=payload["code"],
                    error_message=payload["message"],
                    details=payload["details"],
                ),
                405,
            )
        if request.headers.get("HX-Request") == "true":
            response.headers["X-Toast-Message"] = payload["message"]
            response.headers["X-Toast-Tone"] = "error"
            response.headers["X-Error-Code"] = payload["code"]
        return response

    @app.context_processor
    def inject_request_context():
        return {"current_user": g.get("current_user"), "current_roles": g.get("current_roles", [])}

    return app
