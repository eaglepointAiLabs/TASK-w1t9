"""
Stable rate-limit identity regression: an anonymous caller must stay in the
same rate-limit bucket even if their client_id cookie rotates or disappears.
The server-side fingerprint (remote IP + User-Agent) is the stable anchor.
"""

from __future__ import annotations

from app.extensions import db
from app.repositories.ops_repository import OpsRepository
from app.services.ops_service import OpsService


def _count_buckets(app, prefix: str) -> int:
    with app.app_context():
        return db.session.execute(
            db.text(
                "SELECT COUNT(*) FROM rate_limit_buckets WHERE bucket_key LIKE :p"
            ),
            {"p": f"{prefix}%"},
        ).scalar()


def _sum_requests(app, prefix: str) -> int:
    with app.app_context():
        return db.session.execute(
            db.text(
                "SELECT COALESCE(SUM(request_count), 0) FROM rate_limit_buckets WHERE bucket_key LIKE :p"
            ),
            {"p": f"{prefix}%"},
        ).scalar()


def test_anonymous_actor_stays_in_same_bucket_across_cookie_rotation(app):
    """
    An anonymous caller whose client_id cookie is wiped or rotated between
    requests must map to the SAME rate-limit bucket as long as the remote
    IP and User-Agent are stable. The bucket key must not depend on the
    rotating cookie.
    """
    # Two separate test clients represent "same browser / same network"
    # with the second request missing the cookie entirely (cookie rotated
    # or discarded). Flask test_client() defaults remote_addr to 127.0.0.1
    # and sends the same werkzeug User-Agent, so the fingerprint is stable.
    first_client = app.test_client()
    second_client = app.test_client()
    user_agent = "Mozilla/5.0 (fingerprint-test/1.0)"

    # Warm up against a harmless GET that triggers enforce_rate_limit from
    # the before_request hook.
    first_response = first_client.get(
        "/healthz",
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )
    assert first_response.status_code == 200

    before_count = _sum_requests(app, "anon:")
    bucket_count_before = _count_buckets(app, "anon:")

    # Second client has no cookie at all — a cookie-only rate limiter
    # would give it a fresh bucket, but the fingerprint-based key must
    # send it to the same bucket as the first client.
    second_response = second_client.get(
        "/healthz",
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )
    assert second_response.status_code == 200

    after_count = _sum_requests(app, "anon:")
    bucket_count_after = _count_buckets(app, "anon:")

    assert after_count == before_count + 1, (
        "Second request must increment the same anonymous bucket, not create a fresh one"
    )
    assert bucket_count_after == bucket_count_before, (
        "Cookie rotation must not spawn a new rate-limit bucket"
    )


def test_anonymous_actor_with_different_user_agents_uses_different_buckets(app):
    """
    Sanity: two anonymous callers with clearly different fingerprints
    (different User-Agent strings) do land in separate buckets — the
    fingerprint is doing actual work, not collapsing everyone into one.
    """
    client_a = app.test_client()
    client_b = app.test_client()

    client_a.get(
        "/healthz",
        headers={"User-Agent": "agent-a/1.0", "Accept": "application/json"},
    )
    client_b.get(
        "/healthz",
        headers={"User-Agent": "agent-b/1.0", "Accept": "application/json"},
    )

    bucket_count = _count_buckets(app, "anon:")
    assert bucket_count >= 2, "Distinct fingerprints must map to distinct buckets"


def test_rate_limit_actor_key_separates_authenticated_from_anonymous(app):
    """
    Verify the bucket key format keeps authenticated and anonymous
    identities in separate namespaces. An authenticated user whose
    anonymous fingerprint matches a pre-login visitor must not share
    a bucket with them.
    """
    with app.app_context():
        from app.factory import _rate_limit_actor_key

        class _FakeUser:
            id = "user-123"

        with app.test_request_context("/healthz", headers={"User-Agent": "ua"}):
            auth_key = _rate_limit_actor_key(_FakeUser())
            anon_key = _rate_limit_actor_key(None)

    assert auth_key.startswith("user:")
    assert anon_key.startswith("anon:")
    assert auth_key != anon_key
