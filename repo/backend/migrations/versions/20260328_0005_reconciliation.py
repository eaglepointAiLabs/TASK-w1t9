"""reconciliation schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_0005"
down_revision = "20260328_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reconciliation_runs",
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("imported_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("imported_filename", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("matched_rows", sa.Integer(), nullable=False),
        sa.Column("exception_count", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["imported_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reconciliation_runs_imported_by_user_id"), "reconciliation_runs", ["imported_by_user_id"], unique=False)
    op.create_index(op.f("ix_reconciliation_runs_status"), "reconciliation_runs", ["status"], unique=False)

    op.create_table(
        "reconciliation_rows",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("transaction_reference", sa.String(length=120), nullable=False),
        sa.Column("terminal_status", sa.String(length=40), nullable=False),
        sa.Column("terminal_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("terminal_currency", sa.String(length=8), nullable=False),
        sa.Column("matched_payment_id", sa.String(length=36), nullable=True),
        sa.Column("match_status", sa.String(length=40), nullable=False),
        sa.Column("raw_row_json", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["matched_payment_id"], ["payment_transactions.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["reconciliation_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reconciliation_rows_match_status"), "reconciliation_rows", ["match_status"], unique=False)
    op.create_index(op.f("ix_reconciliation_rows_matched_payment_id"), "reconciliation_rows", ["matched_payment_id"], unique=False)
    op.create_index(op.f("ix_reconciliation_rows_run_id"), "reconciliation_rows", ["run_id"], unique=False)
    op.create_index(op.f("ix_reconciliation_rows_transaction_reference"), "reconciliation_rows", ["transaction_reference"], unique=False)

    op.create_table(
        "reconciliation_exceptions",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("row_id", sa.String(length=36), nullable=False),
        sa.Column("transaction_reference", sa.String(length=120), nullable=False),
        sa.Column("exception_type", sa.String(length=60), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("resolved_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_reason", sa.String(length=255), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["row_id"], ["reconciliation_rows.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["reconciliation_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reconciliation_exceptions_exception_type"), "reconciliation_exceptions", ["exception_type"], unique=False)
    op.create_index(op.f("ix_reconciliation_exceptions_resolved_by_user_id"), "reconciliation_exceptions", ["resolved_by_user_id"], unique=False)
    op.create_index(op.f("ix_reconciliation_exceptions_row_id"), "reconciliation_exceptions", ["row_id"], unique=False)
    op.create_index(op.f("ix_reconciliation_exceptions_run_id"), "reconciliation_exceptions", ["run_id"], unique=False)
    op.create_index(op.f("ix_reconciliation_exceptions_status"), "reconciliation_exceptions", ["status"], unique=False)
    op.create_index(op.f("ix_reconciliation_exceptions_transaction_reference"), "reconciliation_exceptions", ["transaction_reference"], unique=False)

    op.create_table(
        "reconciliation_actions",
        sa.Column("exception_id", sa.String(length=36), nullable=False),
        sa.Column("operator_user_id", sa.String(length=36), nullable=False),
        sa.Column("action_type", sa.String(length=60), nullable=False),
        sa.Column("from_status", sa.String(length=40), nullable=True),
        sa.Column("to_status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["exception_id"], ["reconciliation_exceptions.id"]),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reconciliation_actions_exception_id"), "reconciliation_actions", ["exception_id"], unique=False)
    op.create_index(op.f("ix_reconciliation_actions_operator_user_id"), "reconciliation_actions", ["operator_user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_reconciliation_actions_operator_user_id"), table_name="reconciliation_actions")
    op.drop_index(op.f("ix_reconciliation_actions_exception_id"), table_name="reconciliation_actions")
    op.drop_table("reconciliation_actions")
    op.drop_index(op.f("ix_reconciliation_exceptions_transaction_reference"), table_name="reconciliation_exceptions")
    op.drop_index(op.f("ix_reconciliation_exceptions_status"), table_name="reconciliation_exceptions")
    op.drop_index(op.f("ix_reconciliation_exceptions_run_id"), table_name="reconciliation_exceptions")
    op.drop_index(op.f("ix_reconciliation_exceptions_row_id"), table_name="reconciliation_exceptions")
    op.drop_index(op.f("ix_reconciliation_exceptions_resolved_by_user_id"), table_name="reconciliation_exceptions")
    op.drop_index(op.f("ix_reconciliation_exceptions_exception_type"), table_name="reconciliation_exceptions")
    op.drop_table("reconciliation_exceptions")
    op.drop_index(op.f("ix_reconciliation_rows_transaction_reference"), table_name="reconciliation_rows")
    op.drop_index(op.f("ix_reconciliation_rows_run_id"), table_name="reconciliation_rows")
    op.drop_index(op.f("ix_reconciliation_rows_matched_payment_id"), table_name="reconciliation_rows")
    op.drop_index(op.f("ix_reconciliation_rows_match_status"), table_name="reconciliation_rows")
    op.drop_table("reconciliation_rows")
    op.drop_index(op.f("ix_reconciliation_runs_status"), table_name="reconciliation_runs")
    op.drop_index(op.f("ix_reconciliation_runs_imported_by_user_id"), table_name="reconciliation_runs")
    op.drop_table("reconciliation_runs")
