from __future__ import annotations

from flask import g, make_response, redirect, request, url_for


def attach_feedback(response, message: str | None = None, tone: str = "success", redirect_to: str | None = None):
    wrapped = make_response(response)
    if request.headers.get("HX-Request") == "true":
        if message:
            wrapped.headers["X-Toast-Message"] = message
            wrapped.headers["X-Toast-Tone"] = tone
        if redirect_to:
            wrapped.headers["X-Redirect-Location"] = redirect_to
    return wrapped


def redirect_anonymous_to_login():
    if g.get("current_user") is None:
        destination = url_for("auth.render_login_page")
        if request.headers.get("HX-Request") == "true":
            return attach_feedback(("", 401), "Please sign in to continue.", tone="warning", redirect_to=destination)
        return redirect(destination)
    return None
