from app.extensions import db
from app.repositories.auth_repository import AuthRepository
from app.repositories.community_repository import CommunityRepository
from app.services.community_service import CommunityService


def test_block_behavior_and_report_validation(app):
    with app.app_context():
        repo = CommunityRepository()
        service = CommunityService(repo)
        customer = AuthRepository().get_user_by_username("customer")
        moderator = AuthRepository().get_user_by_username("moderator")
        post = repo.list_posts()[0]
        service.block_user(customer.id, moderator.id)

        blocked = False
        try:
            service.create_comment(moderator, {"target_type": "post", "target_id": post.id, "body": "Hello there"})
        except Exception as exc:
            blocked = getattr(exc, "code", "") == "blocked_interaction"
        assert blocked


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
