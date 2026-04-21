from unittest.mock import patch

from app.extensions import db
from app.repositories.auth_repository import AuthRepository
from app.repositories.community_repository import CommunityRepository
from app.repositories.moderation_repository import ModerationRepository
from app.services.community_service import CommunityService
from app.services.errors import AppError
from app.services.moderation_service import ModerationService


def test_report_creation_is_atomic_with_queue_item(app):
    """
    If ensure_queue_item_for_report raises after the report flush, the report
    must not be committed — create_report owns the transaction boundary and
    rolls back on any failure so both rows land together or neither does.
    The caller does not need to rollback explicitly.
    """
    with app.app_context():
        customer = AuthRepository().get_user_by_username("customer")
        post = CommunityRepository().list_posts()[0]

        before = db.session.scalar(db.text("SELECT COUNT(*) FROM reports"))

        with patch.object(
            ModerationService,
            "ensure_queue_item_for_report",
            side_effect=RuntimeError("simulated queue insertion failure"),
        ):
            raised = False
            try:
                CommunityService(CommunityRepository()).create_report(
                    customer,
                    {"target_type": "post", "target_id": post.id, "reason_code": "spam", "details": "test"},
                )
            except RuntimeError:
                raised = True
            assert raised, "create_report must propagate the underlying failure"

        after = db.session.scalar(db.text("SELECT COUNT(*) FROM reports"))
        assert after == before, "Report must not be persisted when queue-item insertion fails"


def test_ensure_queue_item_is_idempotent(app):
    """
    Re-invoking ensure_queue_item_for_report for the same report must not
    create duplicate queue items — this keeps retries safe if the first
    commit succeeded but a downstream step later retries.
    """
    with app.app_context():
        customer = AuthRepository().get_user_by_username("customer")
        post = CommunityRepository().list_posts()[0]
        report = CommunityService(CommunityRepository()).create_report(
            customer,
            {"target_type": "post", "target_id": post.id, "reason_code": "abuse", "details": "dup-check"},
        )

        moderation = ModerationService(ModerationRepository())
        moderation.ensure_queue_item_for_report(report)
        moderation.ensure_queue_item_for_report(report)
        db.session.commit()

        count = db.session.scalar(
            db.text("SELECT COUNT(*) FROM moderation_queue WHERE report_id = :rid"),
            {"rid": report.id},
        )
        assert count == 1


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
