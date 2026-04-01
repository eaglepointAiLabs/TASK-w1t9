from app.repositories.auth_repository import AuthRepository
from app.repositories.community_repository import CommunityRepository
from app.repositories.moderation_repository import ModerationRepository
from app.services.community_service import CommunityService
from app.services.errors import AppError
from app.services.moderation_service import ModerationService


def test_report_creates_queue_item_and_reason_required(app):
    with app.app_context():
        customer = AuthRepository().get_user_by_username("customer")
        post = CommunityRepository().list_posts()[0]
        report = CommunityService(CommunityRepository()).create_report(
            customer,
            {"target_type": "post", "target_id": post.id, "reason_code": "abuse", "details": "abusive language"},
        )
        queue = ModerationService(ModerationRepository()).list_queue(["Moderator"])
        assert any(item.report_id == report.id for item in queue)

        item = next(item for item in queue if item.report_id == report.id)
        failed = False
        try:
            ModerationService(ModerationRepository()).decide_item(
                item.id,
                {"outcome": "remove", "reason_code": "", "operator_notes": ""},
                AuthRepository().get_user_by_username("moderator"),
                ["Moderator"],
            )
        except Exception as exc:
            failed = getattr(exc, "code", "") == "validation_error"
        assert failed


def test_role_change_requires_nonce(app):
    with app.app_context():
        service = ModerationService(ModerationRepository())
        finance = AuthRepository().get_user_by_username("finance")
        failed = False
        try:
            service.change_role(
                {"target_username": "customer", "role_name": "Moderator", "action": "grant"},
                finance,
                ["Finance Admin"],
                None,
                None,
            )
        except Exception as exc:
            failed = getattr(exc, "code", "") == "nonce_required"
        assert failed


def test_moderator_cannot_change_roles(app):
    with app.app_context():
        service = ModerationService(ModerationRepository())
        moderator = AuthRepository().get_user_by_username("moderator")
        try:
            service.change_role(
                {
                    "target_username": "customer",
                    "role_name": "Moderator",
                    "action": "grant",
                },
                moderator,
                ["Moderator"],
                "session-id",
                "nonce-value",
            )
            assert False
        except AppError as exc:
            assert exc.code == "forbidden"


def test_finance_admin_cannot_change_own_roles(app):
    with app.app_context():
        service = ModerationService(ModerationRepository())
        finance = AuthRepository().get_user_by_username("finance")
        try:
            service.change_role(
                {
                    "target_username": "finance",
                    "role_name": "Moderator",
                    "action": "grant",
                },
                finance,
                ["Finance Admin"],
                "session-id",
                "nonce-value",
            )
            assert False
        except AppError as exc:
            assert exc.code == "forbidden"
