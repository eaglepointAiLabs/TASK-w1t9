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


def test_partial_multi_refund_math_with_low_risk_auto_approval(app):
    with app.app_context():
        payment = _create_success_payment()
        finance = AuthRepository().get_user_by_username("finance")
        session = AuthRepository().create_session(finance.id, "refund-session-low-risk", payment.created_at)
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


def test_high_risk_refund_requires_store_manager_approval(app):
    with app.app_context():
        payment = _create_success_payment()
        finance = AuthRepository().get_user_by_username("finance")
        manager = AuthRepository().get_user_by_username("manager")
        finance_session = AuthRepository().create_session(finance.id, "refund-session-finance", payment.created_at)
        manager_session = AuthRepository().create_session(manager.id, "refund-session-manager", payment.created_at)
        db.session.commit()

        service = RefundService(RefundRepository())
        refund = service.create_refund(
            {"transaction_reference": payment.transaction_reference, "refund_amount": "60.00", "route": payment.channel},
            finance,
            ["Finance Admin"],
            finance_session.id,
            _issue_nonce(finance_session.id, "refund:create"),
            "device-b",
        )
        assert refund.status == "pending_stepup"

        forbidden = False
        try:
            service.confirm_stepup(
                refund.id,
                "Finance#12345",
                finance,
                ["Finance Admin"],
                finance_session.id,
                _issue_nonce(finance_session.id, "refund:approve"),
            )
        except Exception as exc:
            forbidden = getattr(exc, "code", "") == "forbidden"
        assert forbidden

        approved = service.confirm_stepup(
            refund.id,
            "Manager#12345",
            manager,
            ["Store Manager"],
            manager_session.id,
            _issue_nonce(manager_session.id, "refund:approve"),
        )
        assert approved.status == "approved"
        assert any(event.event_type == "manager_stepup_approved" for event in approved.events)


def test_nonce_replay_still_blocks_refund_request(app):
    with app.app_context():
        payment = _create_success_payment()
        finance = AuthRepository().get_user_by_username("finance")
        session = AuthRepository().create_session(finance.id, "refund-session-replay", payment.created_at)
        db.session.commit()
        service = RefundService(RefundRepository())
        nonce = _issue_nonce(session.id, "refund:create")
        refund = service.create_refund(
            {"transaction_reference": payment.transaction_reference, "refund_amount": "60.00", "route": payment.channel},
            finance,
            ["Finance Admin"],
            session.id,
            nonce,
            "device-c",
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
                "device-c",
            )
        except Exception as exc:
            replay_blocked = getattr(exc, "code", "") == "nonce_invalid"
        assert replay_blocked


def test_device_anomaly_detection_requires_manager_approval(app):
    with app.app_context():
        payment = _create_success_payment()
        finance = AuthRepository().get_user_by_username("finance")
        session = AuthRepository().create_session(finance.id, "refund-session-device-risk", payment.created_at)
        db.session.commit()
        service = RefundService(RefundRepository())
        for index in range(3):
            service.create_refund(
                {
                    "transaction_reference": payment.transaction_reference,
                    "refund_amount": "1.00",
                    "route": payment.channel,
                },
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


def test_refund_rejects_exceeding_captured_amount(app):
    with app.app_context():
        payment = _create_success_payment()
        finance = AuthRepository().get_user_by_username("finance")
        session = AuthRepository().create_session(finance.id, "refund-session-cap", payment.created_at)
        db.session.commit()
        service = RefundService(RefundRepository())

        exceeded = False
        try:
            service.create_refund(
                {"transaction_reference": payment.transaction_reference, "refund_amount": "999.99", "route": payment.channel},
                finance,
                ["Finance Admin"],
                session.id,
                _issue_nonce(session.id, "refund:create"),
                "device-cap",
            )
        except Exception as exc:
            exceeded = getattr(exc, "code", "") == "refund_cap_exceeded"
        assert exceeded


def test_refund_rejects_wrong_route(app):
    with app.app_context():
        payment = _create_success_payment()
        finance = AuthRepository().get_user_by_username("finance")
        session = AuthRepository().create_session(finance.id, "refund-session-route", payment.created_at)
        db.session.commit()
        service = RefundService(RefundRepository())

        wrong_route = False
        try:
            service.create_refund(
                {"transaction_reference": payment.transaction_reference, "refund_amount": "5.00", "route": "wrong_channel"},
                finance,
                ["Finance Admin"],
                session.id,
                _issue_nonce(session.id, "refund:create"),
                "device-route",
            )
        except Exception as exc:
            wrong_route = getattr(exc, "code", "") == "original_route_required"
        assert wrong_route


def test_refund_rejects_non_success_payment(app):
    with app.app_context():
        customer_id = AuthRepository().get_user_by_username("customer").id
        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")
        order_service = OrderService(OrderRepository(), CatalogRepository())
        order_service.add_cart_item(customer_id, {"dish_id": dish.id, "quantity": 1, "selected_options": {}})
        order = order_service.checkout(customer_id, f"refund-pending-{dish.id[:4]}")
        payment = PaymentService(PaymentRepository()).capture_payment(
            {"order_id": order.id, "transaction_reference": f"refund-pending-pay-{order.id[:6]}", "capture_amount": "10.00", "status": "pending"},
            ["Finance Admin"],
        )

        finance = AuthRepository().get_user_by_username("finance")
        session = AuthRepository().create_session(finance.id, "refund-session-pending", payment.created_at)
        db.session.commit()
        service = RefundService(RefundRepository())

        non_success = False
        try:
            service.create_refund(
                {"transaction_reference": payment.transaction_reference, "refund_amount": "5.00", "route": payment.channel},
                finance,
                ["Finance Admin"],
                session.id,
                _issue_nonce(session.id, "refund:create"),
                "device-pending",
            )
        except Exception as exc:
            non_success = getattr(exc, "code", "") == "validation_error"
        assert non_success


def test_refund_rejects_nonexistent_payment(app):
    with app.app_context():
        finance = AuthRepository().get_user_by_username("finance")
        session = AuthService(AuthRepository()).create_session_for_user(finance.id, 12)
        service = RefundService(RefundRepository())

        not_found = False
        try:
            service.create_refund(
                {"transaction_reference": "nonexistent-ref", "refund_amount": "5.00", "route": "offline_wechat_simulator"},
                finance,
                ["Finance Admin"],
                session.id,
                _issue_nonce(session.id, "refund:create"),
                "device-nf",
            )
        except Exception as exc:
            not_found = getattr(exc, "code", "") == "not_found"
        assert not_found


def test_get_refund_returns_not_found(app):
    with app.app_context():
        service = RefundService(RefundRepository())
        not_found = False
        try:
            service.get_refund("nonexistent-refund-id", ["Finance Admin"])
        except Exception as exc:
            not_found = getattr(exc, "code", "") == "not_found"
        assert not_found


def test_refund_requires_finance_admin_role(app):
    with app.app_context():
        service = RefundService(RefundRepository())
        forbidden = False
        try:
            service.list_risk_events(["Customer"])
        except Exception as exc:
            forbidden = getattr(exc, "code", "") == "forbidden"
        assert forbidden
