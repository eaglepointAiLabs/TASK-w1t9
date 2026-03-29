from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    PaymentTransaction,
    ReconciliationAction,
    ReconciliationException,
    ReconciliationRow,
    ReconciliationRun,
)


class ReconciliationRepository:
    def create_run(self, **kwargs) -> ReconciliationRun:
        run = ReconciliationRun(**kwargs)
        db.session.add(run)
        db.session.flush()
        return run

    def add_row(self, **kwargs) -> ReconciliationRow:
        row = ReconciliationRow(**kwargs)
        db.session.add(row)
        db.session.flush()
        return row

    def add_exception(self, **kwargs) -> ReconciliationException:
        exception = ReconciliationException(**kwargs)
        db.session.add(exception)
        db.session.flush()
        return exception

    def add_action(self, **kwargs) -> ReconciliationAction:
        action = ReconciliationAction(**kwargs)
        db.session.add(action)
        db.session.flush()
        return action

    def list_runs(self) -> list[ReconciliationRun]:
        stmt = select(ReconciliationRun).order_by(ReconciliationRun.created_at.desc())
        return list(db.session.scalars(stmt))

    def get_run(self, run_id: str) -> ReconciliationRun | None:
        stmt = (
            select(ReconciliationRun)
            .options(
                joinedload(ReconciliationRun.rows),
                joinedload(ReconciliationRun.exceptions).joinedload(ReconciliationException.actions),
            )
            .where(ReconciliationRun.id == run_id)
        )
        return db.session.execute(stmt).unique().scalar_one_or_none()

    def get_exception(self, exception_id: str) -> ReconciliationException | None:
        stmt = (
            select(ReconciliationException)
            .options(joinedload(ReconciliationException.actions))
            .where(ReconciliationException.id == exception_id)
        )
        return db.session.execute(stmt).unique().scalar_one_or_none()

    def find_payments_by_reference(self, reference: str) -> list[PaymentTransaction]:
        stmt = select(PaymentTransaction).where(PaymentTransaction.transaction_reference == reference)
        return list(db.session.scalars(stmt))

    def list_exceptions_for_run(self, run_id: str) -> list[ReconciliationException]:
        stmt = select(ReconciliationException).where(ReconciliationException.run_id == run_id)
        return list(db.session.scalars(stmt))
