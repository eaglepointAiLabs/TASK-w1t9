from __future__ import annotations

import csv
import json
from io import StringIO

import structlog

from app.extensions import db
from app.repositories.reconciliation_repository import ReconciliationRepository
from app.services.catalog_validation import parse_price
from app.services.errors import AppError
from app.services.rbac_service import RBACService
from app.services.time_utils import utc_now_naive


logger = structlog.get_logger(__name__)

REQUIRED_COLUMNS = {"transaction_reference", "amount", "currency", "status"}


class ReconciliationService:
    def __init__(self, repository: ReconciliationRepository) -> None:
        self.repository = repository
        self.rbac = RBACService()

    def import_csv(
        self,
        csv_text: str,
        source_name: str,
        imported_filename: str,
        operator_user_id: str,
        current_roles: list[str],
    ):
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        reader = csv.DictReader(StringIO(csv_text))
        if reader.fieldnames is None:
            raise AppError("validation_error", "CSV header row is required.", 400)
        missing_columns = REQUIRED_COLUMNS.difference(set(reader.fieldnames))
        if missing_columns:
            raise AppError(
                "validation_error",
                "CSV is missing required columns.",
                400,
                {"missing_columns": sorted(missing_columns)},
            )

        run = self.repository.create_run(
            source_name=source_name or "terminal_csv",
            imported_by_user_id=operator_user_id,
            imported_filename=imported_filename or "",
            status="completed",
        )

        seen_references: set[str] = set()
        matched_rows = 0
        exception_count = 0

        for row_number, row in enumerate(reader, start=2):
            reference = (row.get("transaction_reference") or "").strip()
            if not reference:
                raise AppError("validation_error", "transaction_reference cannot be blank.", 400, {"row_number": row_number})
            amount = parse_price(row.get("amount"), "amount")
            status = (row.get("status") or "").strip().lower()
            currency = (row.get("currency") or "USD").strip().upper()

            payments = self.repository.find_payments_by_reference(reference)
            match_status = "matched"
            exception_type = None
            details = {"terminal_row": row}

            if reference in seen_references:
                match_status = "exception"
                exception_type = "duplicate_reference"
                details["reason"] = "Statement contains the same transaction reference more than once."
            elif not payments:
                match_status = "exception"
                exception_type = "missing_local_transaction"
                details["reason"] = "No local payment transaction matched the statement reference."
            elif len(payments) > 1:
                match_status = "exception"
                exception_type = "duplicate_reference"
                details["reason"] = "Multiple local payment transactions share the reference."
            else:
                payment = payments[0]
                details["payment_status"] = payment.status
                details["payment_amount"] = f"{payment.capture_amount:.2f}"
                if payment.capture_amount != amount:
                    match_status = "exception"
                    exception_type = "amount_mismatch"
                    details["reason"] = "Terminal amount does not match local capture amount."
                elif payment.status.lower() != status:
                    match_status = "exception"
                    exception_type = "status_mismatch"
                    details["reason"] = "Terminal status does not match local transaction status."

            matched_payment_id = payments[0].id if len(payments) == 1 else None
            rec_row = self.repository.add_row(
                run_id=run.id,
                row_number=row_number,
                transaction_reference=reference,
                terminal_status=status,
                terminal_amount=amount,
                terminal_currency=currency,
                matched_payment_id=matched_payment_id,
                match_status=match_status,
                raw_row_json=json.dumps(row),
            )

            if exception_type is not None:
                self.repository.add_exception(
                    run_id=run.id,
                    row_id=rec_row.id,
                    transaction_reference=reference,
                    exception_type=exception_type,
                    details_json=json.dumps(details),
                    status="open",
                )
                exception_count += 1
            else:
                matched_rows += 1

            seen_references.add(reference)

        run.total_rows = max(0, row_number - 1) if "row_number" in locals() else 0
        run.matched_rows = matched_rows
        run.exception_count = exception_count
        run.status = "completed_with_exceptions" if exception_count else "completed"
        db.session.add(run)
        db.session.commit()
        logger.info(
            "reconciliation.run_imported",
            run_id=run.id,
            total_rows=run.total_rows,
            matched_rows=matched_rows,
            exception_count=exception_count,
        )
        return run

    def list_runs(self, current_roles: list[str]):
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        return self.repository.list_runs()

    def get_run(self, run_id: str, current_roles: list[str]):
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        run = self.repository.get_run(run_id)
        if run is None:
            raise AppError("not_found", "Reconciliation run not found.", 404)
        return run

    def resolve_exception(
        self,
        exception_id: str,
        action_type: str,
        reason: str,
        operator_user_id: str,
        current_roles: list[str],
    ):
        self.rbac.require_roles(current_roles, ["Finance Admin"])
        exception = self.repository.get_exception(exception_id)
        if exception is None:
            raise AppError("not_found", "Reconciliation exception not found.", 404)
        if exception.status == "resolved":
            raise AppError("validation_error", "Exception is already resolved.", 400)

        from_status = exception.status
        to_status = "resolved" if action_type == "resolve" else "open"
        exception.status = to_status
        exception.resolved_by_user_id = operator_user_id if to_status == "resolved" else None
        exception.resolved_at = utc_now_naive() if to_status == "resolved" else None
        exception.resolution_reason = reason.strip()
        db.session.add(exception)
        self.repository.add_action(
            exception_id=exception.id,
            operator_user_id=operator_user_id,
            action_type=action_type,
            from_status=from_status,
            to_status=to_status,
            reason=reason.strip(),
        )

        run = self.repository.get_run(exception.run_id)
        open_exceptions = [item for item in run.exceptions if item.id != exception.id and item.status != "resolved"]
        if to_status == "resolved":
            run.exception_count = len(open_exceptions)
        run.status = "completed" if not open_exceptions and to_status == "resolved" else "completed_with_exceptions"
        db.session.add(run)
        db.session.commit()
        logger.info("reconciliation.exception_resolved", exception_id=exception.id, action_type=action_type, to_status=to_status)
        return exception
