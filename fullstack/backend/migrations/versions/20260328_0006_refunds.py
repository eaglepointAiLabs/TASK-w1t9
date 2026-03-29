"""refunds schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_0006"
down_revision = "20260328_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refunds",
        sa.Column("payment_transaction_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("transaction_reference", sa.String(length=120), nullable=False),
        sa.Column("refund_reference", sa.String(length=120), nullable=False),
        sa.Column("original_route", sa.String(length=80), nullable=False),
        sa.Column("requested_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("hold_reason", sa.String(length=255), nullable=False),
        sa.Column("stepup_required", sa.String(length=5), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["payment_transaction_id"], ["payment_transactions.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refund_reference"),
    )
    op.create_index(op.f("ix_refunds_device_id"), "refunds", ["device_id"], unique=False)
    op.create_index(op.f("ix_refunds_order_id"), "refunds", ["order_id"], unique=False)
    op.create_index(op.f("ix_refunds_payment_transaction_id"), "refunds", ["payment_transaction_id"], unique=False)
    op.create_index(op.f("ix_refunds_refund_reference"), "refunds", ["refund_reference"], unique=True)
    op.create_index(op.f("ix_refunds_requested_by_user_id"), "refunds", ["requested_by_user_id"], unique=False)
    op.create_index(op.f("ix_refunds_status"), "refunds", ["status"], unique=False)
    op.create_index(op.f("ix_refunds_transaction_reference"), "refunds", ["transaction_reference"], unique=False)

    op.create_table(
        "refund_events",
        sa.Column("refund_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("from_status", sa.String(length=40), nullable=True),
        sa.Column("to_status", sa.String(length=40), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["refund_id"], ["refunds.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_refund_events_actor_user_id"), "refund_events", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_refund_events_refund_id"), "refund_events", ["refund_id"], unique=False)

    op.create_table(
        "refund_risk_events",
        sa.Column("refund_id", sa.String(length=36), nullable=True),
        sa.Column("payment_transaction_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("risk_code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("action_taken", sa.String(length=40), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["payment_transaction_id"], ["payment_transactions.id"]),
        sa.ForeignKeyConstraint(["refund_id"], ["refunds.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_refund_risk_events_device_id"), "refund_risk_events", ["device_id"], unique=False)
    op.create_index(op.f("ix_refund_risk_events_payment_transaction_id"), "refund_risk_events", ["payment_transaction_id"], unique=False)
    op.create_index(op.f("ix_refund_risk_events_refund_id"), "refund_risk_events", ["refund_id"], unique=False)
    op.create_index(op.f("ix_refund_risk_events_risk_code"), "refund_risk_events", ["risk_code"], unique=False)

    op.create_table(
        "manager_stepup_challenges",
        sa.Column("refund_id", sa.String(length=36), nullable=False),
        sa.Column("operator_user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["refund_id"], ["refunds.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_manager_stepup_challenges_expires_at"), "manager_stepup_challenges", ["expires_at"], unique=False)
    op.create_index(op.f("ix_manager_stepup_challenges_operator_user_id"), "manager_stepup_challenges", ["operator_user_id"], unique=False)
    op.create_index(op.f("ix_manager_stepup_challenges_refund_id"), "manager_stepup_challenges", ["refund_id"], unique=False)
    op.create_index(op.f("ix_manager_stepup_challenges_status"), "manager_stepup_challenges", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_manager_stepup_challenges_status"), table_name="manager_stepup_challenges")
    op.drop_index(op.f("ix_manager_stepup_challenges_refund_id"), table_name="manager_stepup_challenges")
    op.drop_index(op.f("ix_manager_stepup_challenges_operator_user_id"), table_name="manager_stepup_challenges")
    op.drop_index(op.f("ix_manager_stepup_challenges_expires_at"), table_name="manager_stepup_challenges")
    op.drop_table("manager_stepup_challenges")
    op.drop_index(op.f("ix_refund_risk_events_risk_code"), table_name="refund_risk_events")
    op.drop_index(op.f("ix_refund_risk_events_refund_id"), table_name="refund_risk_events")
    op.drop_index(op.f("ix_refund_risk_events_payment_transaction_id"), table_name="refund_risk_events")
    op.drop_index(op.f("ix_refund_risk_events_device_id"), table_name="refund_risk_events")
    op.drop_table("refund_risk_events")
    op.drop_index(op.f("ix_refund_events_refund_id"), table_name="refund_events")
    op.drop_index(op.f("ix_refund_events_actor_user_id"), table_name="refund_events")
    op.drop_table("refund_events")
    op.drop_index(op.f("ix_refunds_transaction_reference"), table_name="refunds")
    op.drop_index(op.f("ix_refunds_status"), table_name="refunds")
    op.drop_index(op.f("ix_refunds_requested_by_user_id"), table_name="refunds")
    op.drop_index(op.f("ix_refunds_refund_reference"), table_name="refunds")
    op.drop_index(op.f("ix_refunds_payment_transaction_id"), table_name="refunds")
    op.drop_index(op.f("ix_refunds_order_id"), table_name="refunds")
    op.drop_index(op.f("ix_refunds_device_id"), table_name="refunds")
    op.drop_table("refunds")
