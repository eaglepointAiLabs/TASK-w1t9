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


def test_malformed_callback_timestamp_is_rejected_without_exception(app):
    order = _create_order(app)
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        payment = payment_service.capture_payment(
            {
                "order_id": order.id,
                "transaction_reference": "pay-bad-timestamp-1",
                "capture_amount": "10.25",
                "status": "pending",
            },
            ["Finance Admin"],
        )

        bad_timestamp_package = _package(
            "simulator-secret-v1",
            "simulator-v1",
            payment.transaction_reference,
            "not-an-iso-datetime",
        )
        verification = payment_service.verify_callback_preview(bad_timestamp_package, ["Finance Admin"])

        assert verification["verified"] is False
        assert "occurred_at" in verification["message"]


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


def test_jsapi_simulator_generates_and_imports_callback(app):
    order = _create_order(app)
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        payment = payment_service.capture_payment(
            {
                "order_id": order.id,
                "transaction_reference": "pay-sim-unit-1",
                "capture_amount": "10.25",
                "status": "pending",
            },
            ["Finance Admin"],
        )

        result = payment_service.simulate_jsapi_callback(
            {
                "transaction_reference": payment.transaction_reference,
                "status": "success",
                "key_id": "simulator-v1",
            },
            ["Finance Admin"],
        )

        assert result["import_result"]["code"] == "ok"
        assert result["package"]["key_id"] == "simulator-v1"
        refreshed = PaymentRepository().get_transaction(payment.id)
        assert refreshed.status == "success"
        assert len(refreshed.callbacks) >= 1


def test_capture_payment_rejects_nonexistent_order(app):
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        try:
            payment_service.capture_payment(
                {"order_id": "nonexistent-order", "transaction_reference": "test-1", "capture_amount": "10.00", "status": "pending"},
                ["Finance Admin"],
            )
            assert False, "Should have raised"
        except Exception as exc:
            assert getattr(exc, "code", "") == "not_found"


def test_capture_payment_requires_finance_admin_role(app):
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        try:
            payment_service.capture_payment(
                {"order_id": "any", "transaction_reference": "test-1", "capture_amount": "10.00", "status": "pending"},
                ["Customer"],
            )
            assert False, "Should have raised"
        except Exception as exc:
            assert getattr(exc, "code", "") == "forbidden"


def test_get_payment_returns_not_found_for_invalid_id(app):
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        try:
            payment_service.get_payment("nonexistent-payment-id", ["Finance Admin"])
            assert False, "Should have raised"
        except Exception as exc:
            assert getattr(exc, "code", "") == "not_found"


def test_jsapi_simulator_rejects_invalid_status(app):
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        try:
            payment_service.simulate_jsapi_callback(
                {"transaction_reference": "test-ref", "status": "invalid_status", "key_id": "simulator-v1"},
                ["Finance Admin"],
            )
            assert False, "Should have raised"
        except Exception as exc:
            assert getattr(exc, "code", "") == "validation_error"


def test_jsapi_simulator_rejects_missing_reference(app):
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        try:
            payment_service.simulate_jsapi_callback(
                {"transaction_reference": "", "status": "success", "key_id": "simulator-v1"},
                ["Finance Admin"],
            )
            assert False, "Should have raised"
        except Exception as exc:
            assert getattr(exc, "code", "") == "validation_error"


def test_verify_callback_rejects_missing_fields(app):
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        try:
            payment_service.verify_callback_preview({"key_id": "", "signature": "", "payload": {}}, ["Finance Admin"])
            assert False, "Should have raised"
        except Exception as exc:
            assert getattr(exc, "code", "") == "validation_error"


def test_import_callback_rejects_reference_mismatch(app):
    order = _create_order(app)
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        payment = payment_service.capture_payment(
            {"order_id": order.id, "transaction_reference": "pay-mismatch-1", "capture_amount": "10.25", "status": "pending"},
            ["Finance Admin"],
        )
        mismatched_package = _package("simulator-secret-v1", "simulator-v1", "pay-mismatch-1", "2026-03-28T10:00:00+00:00")
        mismatched_package["transaction_reference"] = "different-reference"

        try:
            payment_service.import_callback(mismatched_package, ["Finance Admin"])
            assert False, "Should have raised reference_mismatch"
        except Exception as exc:
            assert getattr(exc, "code", "") == "reference_mismatch"


def test_verify_callback_rejects_reference_mismatch(app):
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        mismatched_package = _package("simulator-secret-v1", "simulator-v1", "verify-ref-1", "2026-03-28T10:00:00+00:00")
        mismatched_package["transaction_reference"] = "different-reference"

        try:
            payment_service.verify_callback_preview(mismatched_package, ["Finance Admin"])
            assert False, "Should have raised reference_mismatch"
        except Exception as exc:
            assert getattr(exc, "code", "") == "reference_mismatch"


def test_import_callback_rejects_payload_missing_transaction_reference(app):
    order = _create_order(app)
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        payment_service.capture_payment(
            {"order_id": order.id, "transaction_reference": "pay-omit-ref-1", "capture_amount": "10.25", "status": "pending"},
            ["Finance Admin"],
        )
        package_without_payload_ref = {
            "key_id": "simulator-v1",
            "signature": "some-signature",
            "transaction_reference": "pay-omit-ref-1",
            "payload": {"status": "success", "occurred_at": "2026-03-28T10:00:00+00:00"},
        }

        try:
            payment_service.import_callback(package_without_payload_ref, ["Finance Admin"])
            assert False, "Should have raised reference_mismatch"
        except Exception as exc:
            assert getattr(exc, "code", "") in ("reference_mismatch", "validation_error")


def test_verify_callback_rejects_payload_missing_transaction_reference(app):
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        package_without_payload_ref = {
            "key_id": "simulator-v1",
            "signature": "some-signature",
            "transaction_reference": "verify-omit-ref-1",
            "payload": {"status": "success", "occurred_at": "2026-03-28T10:00:00+00:00"},
        }

        try:
            payment_service.verify_callback_preview(package_without_payload_ref, ["Finance Admin"])
            assert False, "Should have raised"
        except Exception as exc:
            assert getattr(exc, "code", "") in ("reference_mismatch", "validation_error")


def test_import_callback_rejects_empty_top_level_reference(app):
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        try:
            payment_service.import_callback(
                {"key_id": "simulator-v1", "signature": "sig", "payload": {"occurred_at": "2026-03-28T10:00:00+00:00"}, "transaction_reference": ""},
                ["Finance Admin"],
            )
            assert False, "Should have raised"
        except Exception as exc:
            assert getattr(exc, "code", "") == "validation_error"


def test_import_callback_rejects_invalid_payload_status(app):
    """
    A signed callback whose payload.status is outside the allowed set
    {pending, success, failed} must be rejected before mutating the
    transaction row.
    """
    order = _create_order(app)
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        payment = payment_service.capture_payment(
            {
                "order_id": order.id,
                "transaction_reference": "pay-bad-status-1",
                "capture_amount": "10.25",
                "status": "pending",
            },
            ["Finance Admin"],
        )

        package = _package(
            "simulator-secret-v1",
            "simulator-v1",
            payment.transaction_reference,
            "2026-03-28T10:00:00+00:00",
            status="refunded",
        )

        try:
            payment_service.import_callback(package, ["Finance Admin"])
            assert False, "Should have raised validation_error"
        except Exception as exc:
            assert getattr(exc, "code", "") == "validation_error"

        refreshed = PaymentRepository().get_transaction(payment.id)
        assert refreshed.status == "pending", "Transaction status must not be mutated by a rejected callback"
