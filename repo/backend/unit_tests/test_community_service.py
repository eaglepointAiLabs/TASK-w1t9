import pytest

from app.repositories.auth_repository import AuthRepository
from app.repositories.community_repository import CommunityRepository
from app.services.community_service import CommunityService
from app.services.errors import AppError


def test_toggle_like_creates_and_removes(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        post = repo.list_posts()[0]

        result = service.toggle_like(customer.id, {"target_type": "post", "target_id": post.id})
        assert result["active"] is True
        assert result["count"] >= 1

        result = service.toggle_like(customer.id, {"target_type": "post", "target_id": post.id})
        assert result["active"] is False


def test_toggle_favorite_creates_and_removes(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        post = repo.list_posts()[0]

        result = service.toggle_favorite(customer.id, {"target_type": "post", "target_id": post.id})
        assert result["active"] is True

        result = service.toggle_favorite(customer.id, {"target_type": "post", "target_id": post.id})
        assert result["active"] is False


def test_like_rejects_invalid_target_type(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")

        with pytest.raises(AppError) as exc:
            service.toggle_like(customer.id, {"target_type": "invalid", "target_id": "some-id"})
        assert exc.value.code == "validation_error"


def test_like_rejects_nonexistent_target(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")

        with pytest.raises(AppError) as exc:
            service.toggle_like(customer.id, {"target_type": "post", "target_id": "nonexistent-id"})
        assert exc.value.code == "not_found"


def test_create_comment_success(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        post = repo.list_posts()[0]

        comment = service.create_comment(customer, {"target_type": "post", "target_id": post.id, "body": "Great dish!"})
        assert comment.body == "Great dish!"
        assert comment.author_user_id == customer.id


def test_create_comment_rejects_short_body(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        post = repo.list_posts()[0]

        with pytest.raises(AppError) as exc:
            service.create_comment(customer, {"target_type": "post", "target_id": post.id, "body": "ab"})
        assert exc.value.code == "validation_error"


def test_create_report_validates_reason_code(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        post = repo.list_posts()[0]

        with pytest.raises(AppError) as exc:
            service.create_report(customer, {"target_type": "post", "target_id": post.id, "reason_code": "invalid"})
        assert exc.value.code == "validation_error"


def test_create_report_accepts_valid_reason_codes(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        post = repo.list_posts()[0]

        report = service.create_report(customer, {"target_type": "post", "target_id": post.id, "reason_code": "abuse", "details": "test"})
        assert report.status == "open"
        assert report.reason_code == "abuse"


def test_block_user_validates_target_exists(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")

        with pytest.raises(AppError) as exc:
            service.block_user(customer.id, "nonexistent-user-id")
        assert exc.value.code == "not_found"


def test_block_user_rejects_self_block(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")

        with pytest.raises(AppError) as exc:
            service.block_user(customer.id, customer.id)
        assert exc.value.code == "validation_error"


def test_block_user_prevents_duplicate_blocks(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        moderator = AuthRepository().get_user_by_username("moderator")

        result1 = service.block_user(customer.id, moderator.id)
        result2 = service.block_user(customer.id, moderator.id)
        assert result1["blocked_user_id"] == moderator.id
        assert result2["blocked_user_id"] == moderator.id


def test_unblock_user_removes_block(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        moderator = AuthRepository().get_user_by_username("moderator")

        service.block_user(customer.id, moderator.id)
        result = service.unblock_user(customer.id, moderator.id)
        assert result["blocked_user_id"] == moderator.id


def test_unblock_nonexistent_block_returns_404(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        moderator = AuthRepository().get_user_by_username("moderator")

        with pytest.raises(AppError) as exc:
            service.unblock_user(customer.id, moderator.id)
        assert exc.value.code == "not_found"


def test_block_prevents_like_on_blocked_user_post(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        moderator = AuthRepository().get_user_by_username("moderator")
        post = repo.list_posts()[0]
        # customer blocks the post author (moderator is not the author here, use
        # whoever owns the seeded post — block customer → moderator direction so
        # that moderator cannot like customer-authored content)
        service.block_user(moderator.id, customer.id)

        with pytest.raises(AppError) as exc:
            service.toggle_like(moderator.id, {"target_type": "post", "target_id": post.id})
        assert exc.value.code == "blocked_interaction"


def test_block_prevents_favorite_on_blocked_user_post(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        moderator = AuthRepository().get_user_by_username("moderator")
        post = repo.list_posts()[0]
        service.block_user(moderator.id, customer.id)

        with pytest.raises(AppError) as exc:
            service.toggle_favorite(moderator.id, {"target_type": "post", "target_id": post.id})
        assert exc.value.code == "blocked_interaction"


def test_block_prevents_report_on_blocked_user_post(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        moderator = AuthRepository().get_user_by_username("moderator")
        post = repo.list_posts()[0]
        service.block_user(moderator.id, customer.id)

        with pytest.raises(AppError) as exc:
            service.create_report(
                moderator,
                {"target_type": "post", "target_id": post.id, "reason_code": "spam", "details": "test"},
            )
        assert exc.value.code == "blocked_interaction"


def test_block_prevents_comment_on_blocked_user_post(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        moderator = AuthRepository().get_user_by_username("moderator")
        post = repo.list_posts()[0]
        service.block_user(customer.id, moderator.id)

        with pytest.raises(AppError) as exc:
            service.create_comment(
                moderator,
                {"target_type": "post", "target_id": post.id, "body": "Hello there"},
            )
        assert exc.value.code == "blocked_interaction"


def test_throttle_and_cooldown_boundaries(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        post = repo.list_posts()[0]
        service.create_comment(customer, {"target_type": "post", "target_id": post.id, "body": "First comment"})
        cooldown_hit = False
        try:
            service.create_comment(customer, {"target_type": "post", "target_id": post.id, "body": "Second comment"})
        except Exception as exc:
            cooldown_hit = getattr(exc, "code", "") == "cooldown_active"
        assert cooldown_hit


def test_list_posts_returns_posts(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        posts = service.list_posts()
        assert len(posts) > 0
