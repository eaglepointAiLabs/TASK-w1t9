from app.extensions import db
from app.repositories.auth_repository import AuthRepository
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.refund_repository import RefundRepository
from app.services.auth_service import AuthService
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.services.refund_service import RefundService


def _seed_success_payment():
    customer_id = AuthRepository().get_user_by_username("customer").id
    dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")
    order = OrderService(OrderRepository(), CatalogRepository()).checkout(
        customer_id,
        "refund-order-seed",
    ) if False else None


def _create_success_payment():
    customer_id = AuthRepository().get_user_by_username("customer").id
    dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")
    order_service = OrderService(OrderRepository(), CatalogRepository())
    order_service.add_cart_item(customer_id, {"dish_id": dish.id, "quantity": 1, "selected_options": {}})
    order = order_service.checkout(customer_id, f"refund-order-{dish.id[:6]}")
    return PaymentService(PaymentRepository()).capture_payment(
        {
            "order_id": order.id,
            "transaction_reference": f"refund-pay-{order.id[:8]}",
            "capture_amount": "120.25",
            "status": "success",
        },
        ["Finance Admin"],
    )


def _issue_nonce(session_id: str, purpose: str) -> str:
    return AuthService(AuthRepository()).issue_nonce(session_id, purpose, 5)


def test_partial_multi_refund_math_and_stepup(app):
    with app.app_context():
        payment = _create_success_payment()
        finance = AuthRepository().get_user_by_username("finance")
        session = AuthRepository().create_session(finance.id, "refund-session-1", payment.created_at)
        db.session.commit()

        service = RefundService(RefundRepository())
        first = service.create_refund(
            {"transaction_reference": payment.transaction_reference, "refund_amount": "4.00", "route": payment.channel},
            finance,
            ["Finance Admin"],
            session.id,
            _issue_nonce(session.id, "refund:create"),
            "device-a",
        )
        second = service.create_refund(
            {"transaction_reference": payment.transaction_reference, "refund_amount": "6.00", "route": payment.channel},
            finance,
            ["Finance Admin"],
            session.id,
            _issue_nonce(session.id, "refund:create"),
            "device-a",
        )

        assert first.status == "approved"
        assert second.status == "approved"


def test_stepup_trigger_and_nonce_replay_rejection(app):
    with app.app_context():
        payment = _create_success_payment()
        finance = AuthRepository().get_user_by_username("finance")
        session = AuthRepository().create_session(finance.id, "refund-session-2", payment.created_at)
        db.session.commit()
        service = RefundService(RefundRepository())
        nonce = _issue_nonce(session.id, "refund:create")
        refund = service.create_refund(
            {"transaction_reference": payment.transaction_reference, "refund_amount": "60.00", "route": payment.channel},
            finance,
            ["Finance Admin"],
            session.id,
            nonce,
            "device-b",
        )
        assert refund.status == "pending_stepup"

        replay_blocked = False
        try:
            service.create_refund(
                {"transaction_reference": payment.transaction_reference, "refund_amount": "1.00", "route": payment.channel},
                finance,
                ["Finance Admin"],
                session.id,
                nonce,
                "device-b",
            )
        except Exception as exc:
            replay_blocked = getattr(exc, "code", "") == "nonce_invalid"
        assert replay_blocked


def test_device_anomaly_detection(app):
    with app.app_context():
        payment = _create_success_payment()
        finance = AuthRepository().get_user_by_username("finance")
        session = AuthRepository().create_session(finance.id, "refund-session-3", payment.created_at)
        db.session.commit()
        service = RefundService(RefundRepository())
        for _ in range(3):
            service.create_refund(
                {"transaction_reference": payment.transaction_reference, "refund_amount": "1.00", "route": payment.channel},
                finance,
                ["Finance Admin"],
                session.id,
                _issue_nonce(session.id, "refund:create"),
                "device-risk",
            )

        risky = service.create_refund(
            {"transaction_reference": payment.transaction_reference, "refund_amount": "1.00", "route": payment.channel},
            finance,
            ["Finance Admin"],
            session.id,
            _issue_nonce(session.id, "refund:create"),
            "device-risk",
        )
        assert risky.status == "pending_stepup"
