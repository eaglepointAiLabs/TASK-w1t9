from datetime import timedelta

from app.extensions import db
from app.repositories.auth_repository import AuthRepository
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.services.order_service import OrderService
from app.services.payment_security import PaymentSecurity
from app.services.payment_service import PaymentService
from app.services.time_utils import utc_now_naive


def _create_order(app):
    with app.app_context():
        customer_id = AuthRepository().get_user_by_username("customer").id
        dish = CatalogRepository().get_dish_by_slug("citrus-tofu-bowl")
        order_service = OrderService(OrderRepository(), CatalogRepository())
        order_service.add_cart_item(customer_id, {"dish_id": dish.id, "quantity": 1, "selected_options": {}})
        return order_service.checkout(customer_id, "payment-seed-order")


def _package(secret: str, key_id: str, reference: str, occurred_at: str, status: str = "success"):
    payload = {"transaction_reference": reference, "status": status, "occurred_at": occurred_at}
    signer = PaymentSecurity(PaymentSecurity.derive_fernet_key("tablepay-local-encryption-key"))
    return {
        "key_id": key_id,
        "signature": signer.sign_payload(payload, secret),
        "transaction_reference": reference,
        "payload": payload,
        "source_name": "unit-test",
    }


def test_valid_and_invalid_signature_cases(app):
    order = _create_order(app)
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        payment = payment_service.capture_payment(
            {
                "order_id": order.id,
                "transaction_reference": "pay-valid-1",
                "capture_amount": "10.25",
                "status": "pending",
            },
            ["Finance Admin"],
        )

        valid_package = _package("simulator-secret-v1", "simulator-v1", payment.transaction_reference, "2026-03-28T10:00:00+00:00")
        invalid_package = _package("wrong-secret", "simulator-v1", payment.transaction_reference, "2026-03-28T10:00:00+00:00")

        valid = payment_service.verify_callback_preview(valid_package, ["Finance Admin"])
        invalid = payment_service.verify_callback_preview(invalid_package, ["Finance Admin"])

        assert valid["verified"] is True
        assert invalid["verified"] is False


def test_key_rotation_behavior(app):
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        v1 = _package("simulator-secret-v1", "simulator-v1", "rotation-ref-v1", "2026-03-28T10:00:00+00:00")
        v2 = _package("simulator-secret-v2", "simulator-v2", "rotation-ref-v2", "2026-08-01T10:00:00+00:00")
        expired = _package("simulator-secret-v1", "simulator-v1", "rotation-ref-v3", "2026-12-01T10:00:00+00:00")

        assert payment_service.verify_callback_preview(v1, ["Finance Admin"])["verified"] is True
        assert payment_service.verify_callback_preview(v2, ["Finance Admin"])["verified"] is True
        assert payment_service.verify_callback_preview(expired, ["Finance Admin"])["verified"] is False


def test_duplicate_callback_handling_within_and_beyond_window(app):
    order = _create_order(app)
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        payment = payment_service.capture_payment(
            {
                "order_id": order.id,
                "transaction_reference": "pay-dedup-1",
                "capture_amount": "10.25",
                "status": "pending",
            },
            ["Finance Admin"],
        )

        package = _package("simulator-secret-v1", "simulator-v1", payment.transaction_reference, "2026-03-28T10:00:00+00:00")
        first = payment_service.import_callback(package, ["Finance Admin"])
        second = payment_service.import_callback(package, ["Finance Admin"])

        dedup = PaymentRepository().get_any_dedup_key(payment.transaction_reference)
        dedup.expires_at = utc_now_naive() - timedelta(hours=25)
        db.session.add(dedup)
        db.session.commit()

        third = payment_service.import_callback(package, ["Finance Admin"])

        assert first["data"]["callback_id"] == second["data"]["callback_id"]
        assert third["data"]["callback_id"] != first["data"]["callback_id"]
