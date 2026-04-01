from app.extensions import db
from app.repositories.auth_repository import AuthRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reconciliation_repository import ReconciliationRepository
from app.services.errors import AppError
from app.services.payment_service import PaymentService
from app.services.reconciliation_service import ReconciliationService


def _finance_user_id() -> str:
    return AuthRepository().get_user_by_username("finance").id


def test_csv_validation_failure_missing_columns(app):
    with app.app_context():
        service = ReconciliationService(ReconciliationRepository())
        try:
            service.import_csv(
                csv_text="reference,amount\nabc,10.00",
                source_name="terminal_csv",
                imported_filename="bad.csv",
                operator_user_id=_finance_user_id(),
                current_roles=["Finance Admin"],
            )
            assert False, "Expected validation error"
        except AppError as exc:
            assert exc.code == "validation_error"


def test_variance_detection_correctness(app):
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        payment_service.capture_payment(
            {
                "order_id": db.session.execute(db.text("select id from orders limit 1")).scalar(),
                "transaction_reference": "recon-ref-1",
                "capture_amount": "10.25",
                "status": "pending",
            },
            ["Finance Admin"],
        )

        service = ReconciliationService(ReconciliationRepository())
        run = service.import_csv(
            csv_text=(
                "transaction_reference,amount,currency,status\n"
                "recon-ref-1,10.25,USD,success\n"
                "missing-ref,9.99,USD,success\n"
                "recon-ref-1,10.25,USD,success\n"
            ),
            source_name="terminal_csv",
            imported_filename="statement.csv",
            operator_user_id=_finance_user_id(),
            current_roles=["Finance Admin"],
        )

        assert run.total_rows == 3
        assert run.exception_count == 3
        types = {exception.exception_type for exception in run.exceptions}
        assert "status_mismatch" in types
        assert "missing_local_transaction" in types
        assert "duplicate_reference" in types


def test_resolution_workflow_state_transitions(app):
    with app.app_context():
        payment_service = PaymentService(PaymentRepository())
        payment_service.capture_payment(
            {
                "order_id": db.session.execute(db.text("select id from orders limit 1")).scalar(),
                "transaction_reference": "recon-resolve-1",
                "capture_amount": "10.25",
                "status": "pending",
            },
            ["Finance Admin"],
        )
        service = ReconciliationService(ReconciliationRepository())
        run = service.import_csv(
            csv_text="transaction_reference,amount,currency,status\nrecon-resolve-1,10.25,USD,success\n",
            source_name="terminal_csv",
            imported_filename="resolve.csv",
            operator_user_id=_finance_user_id(),
            current_roles=["Finance Admin"],
        )
        exception = run.exceptions[0]

        resolved = service.resolve_exception(
            exception_id=exception.id,
            action_type="resolve",
            reason="Reviewed terminal export and accepted external status.",
            operator_user_id=_finance_user_id(),
            current_roles=["Finance Admin"],
        )

        assert resolved.status == "resolved"
        assert resolved.resolution_reason.startswith("Reviewed terminal export")
        assert resolved.actions[0].to_status == "resolved"
