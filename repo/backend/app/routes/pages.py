from flask import Blueprint

from app.controllers.auth_controller import render_home


pages_bp = Blueprint("pages", __name__)

pages_bp.get("/")(render_home)
