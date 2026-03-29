from flask import Blueprint

from app.controllers.auth_controller import issue_nonce, login, logout, me, render_login_page


auth_bp = Blueprint("auth", __name__)

auth_bp.get("/login")(render_login_page)
auth_bp.post("/auth/login")(login)
auth_bp.post("/auth/logout")(logout)
auth_bp.get("/auth/me")(me)
auth_bp.post("/api/auth/nonces")(issue_nonce)
