from __future__ import annotations

from http.cookies import SimpleCookie
import json
import re
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from uuid import uuid4


_CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


class LiveSession:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookies: dict[str, str] = {}
        self.opener = urllib.request.build_opener()

    def get(self, path: str):
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            headers=self._request_headers(),
            method="GET",
        )
        return self._open(request)

    def post_form(self, path: str, data: dict[str, str], headers: dict[str, str] | None = None):
        body = urllib.parse.urlencode(data).encode("utf-8")
        merged_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if headers:
            merged_headers.update(headers)
        merged_headers = self._request_headers(merged_headers)
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=merged_headers,
            method="POST",
        )
        return self._open(request)

    def post_json(self, path: str, data: dict, headers: dict[str, str] | None = None):
        body = json.dumps(data).encode("utf-8")
        merged_headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if headers:
            merged_headers.update(headers)
        merged_headers = self._request_headers(merged_headers)
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=merged_headers,
            method="POST",
        )
        return self._open(request)

    def get_cookie(self, name: str) -> str | None:
        return self.cookies.get(name)

    def _request_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        merged_headers = dict(headers or {})
        if self.cookies:
            merged_headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in self.cookies.items())
        return merged_headers

    def _capture_response_cookies(self, raw_headers) -> None:
        values = raw_headers.get_all("Set-Cookie") or []
        for raw_cookie in values:
            parsed = SimpleCookie()
            parsed.load(raw_cookie)
            for morsel in parsed.values():
                self.cookies[morsel.key] = morsel.value

    def _open(self, request: urllib.request.Request):
        try:
            response = self.opener.open(request, timeout=10)
            self._capture_response_cookies(response.headers)
            body = response.read().decode("utf-8", errors="replace")
            return response.getcode(), body, response.geturl()
        except HTTPError as exc:
            self._capture_response_cookies(exc.headers)
            body = exc.read().decode("utf-8", errors="replace")
            return exc.code, body, exc.geturl()


def _extract_csrf(html: str) -> str:
    match = _CSRF_RE.search(html)
    assert match is not None, "Expected login page to include csrf_token input."
    return match.group(1)


def _login_customer(session: LiveSession) -> str:
    status, html, _ = session.get("/login")
    assert status == 200
    csrf_token = _extract_csrf(html)

    status, body, _ = session.post_json(
        "/auth/login",
        {
            "username": "customer",
            "password": "Customer#1234",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert status == 200
    assert "Login successful" in body
    assert session.get_cookie("tablepay_session") is not None

    # The login flow rotates CSRF; fall back to form token if cookie rotation is disabled.
    return session.get_cookie("csrf_token") or csrf_token


def _register_customer(session: LiveSession) -> tuple[str, str]:
    status, html, _ = session.get("/register")
    assert status == 200
    csrf_token = _extract_csrf(html)
    username = f"live.customer.{uuid4().hex[:8]}"
    password = "LiveCustomer#1234"

    status, body, _ = session.post_json(
        "/auth/register",
        {
            "username": username,
            "password": password,
            "confirm_password": password,
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert status == 201
    assert "Registration successful" in body
    assert session.get_cookie("tablepay_session") is not None
    return username, (session.get_cookie("csrf_token") or csrf_token)


def test_customer_happy_path_live_runtime(base_url: str):
    session = LiveSession(base_url)
    csrf_token = _login_customer(session)

    for path in ["/", "/menu", "/cart", "/community"]:
        status, _, _ = session.get(path)
        assert status == 200, f"Expected 200 for {path}."

    status, body, _ = session.post_json(
        "/auth/logout",
        {},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert status == 200
    assert "Logout successful" in body

    status, body, final_url = session.get("/cart")
    assert status == 200
    assert final_url.endswith("/login")
    assert "Sign in" in body


def test_customer_permission_denied_for_manager_page(base_url: str):
    session = LiveSession(base_url)
    _login_customer(session)

    status, body, _ = session.get("/manager/dishes")
    assert status == 403
    assert "permission" in body.lower()


def test_customer_registration_live_runtime(base_url: str):
    session = LiveSession(base_url)
    username, csrf_token = _register_customer(session)

    status, dashboard_html, _ = session.get("/")
    assert status == 200
    assert username in dashboard_html

    status, body, _ = session.post_json(
        "/auth/logout",
        {},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert status == 200
    assert "Logout successful" in body
