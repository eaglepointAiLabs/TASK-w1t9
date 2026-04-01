"""payments schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_0004"
down_revision = "20260328_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_transactions",
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("transaction_reference", sa.String(length=120), nullable=False),
        sa.Column("channel", sa.String(length=80), nullable=False),
        sa.Column("capture_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_reference"),
    )
    op.create_index(op.f("ix_payment_transactions_order_id"), "payment_transactions", ["order_id"], unique=False)
    op.create_index(op.f("ix_payment_transactions_status"), "payment_transactions", ["status"], unique=False)
    op.create_index(op.f("ix_payment_transactions_transaction_reference"), "payment_transactions", ["transaction_reference"], unique=True)

    op.create_table(
        "payment_callbacks",
        sa.Column("payment_transaction_id", sa.String(length=36), nullable=True),
        sa.Column("transaction_reference", sa.String(length=120), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.String(length=128), nullable=False),
        sa.Column("signature", sa.String(length=255), nullable=False),
        sa.Column("key_id", sa.String(length=120), nullable=False),
        sa.Column("verification_status", sa.String(length=40), nullable=False),
        sa.Column("verification_message", sa.String(length=255), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("duplicate_of_callback_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["duplicate_of_callback_id"], ["payment_callbacks.id"]),
        sa.ForeignKeyConstraint(["payment_transaction_id"], ["payment_transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payment_callbacks_duplicate_of_callback_id"), "payment_callbacks", ["duplicate_of_callback_id"], unique=False)
    op.create_index(op.f("ix_payment_callbacks_key_id"), "payment_callbacks", ["key_id"], unique=False)
    op.create_index(op.f("ix_payment_callbacks_payload_hash"), "payment_callbacks", ["payload_hash"], unique=False)
    op.create_index(op.f("ix_payment_callbacks_payment_transaction_id"), "payment_callbacks", ["payment_transaction_id"], unique=False)
    op.create_index(op.f("ix_payment_callbacks_transaction_reference"), "payment_callbacks", ["transaction_reference"], unique=False)
    op.create_index(op.f("ix_payment_callbacks_verification_status"), "payment_callbacks", ["verification_status"], unique=False)

    op.create_table(
        "callback_dedup_keys",
        sa.Column("transaction_reference", sa.String(length=120), nullable=False),
        sa.Column("callback_id", sa.String(length=36), nullable=False),
        sa.Column("payload_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["callback_id"], ["payment_callbacks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_reference"),
    )
    op.create_index(op.f("ix_callback_dedup_keys_callback_id"), "callback_dedup_keys", ["callback_id"], unique=False)
    op.create_index(op.f("ix_callback_dedup_keys_expires_at"), "callback_dedup_keys", ["expires_at"], unique=False)
    op.create_index(op.f("ix_callback_dedup_keys_transaction_reference"), "callback_dedup_keys", ["transaction_reference"], unique=True)

    op.create_table(
        "gateway_signing_keys",
        sa.Column("key_id", sa.String(length=120), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("algorithm", sa.String(length=40), nullable=False),
        sa.Column("active_from", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_id"),
    )
    op.create_index(op.f("ix_gateway_signing_keys_active_from"), "gateway_signing_keys", ["active_from"], unique=False)
    op.create_index(op.f("ix_gateway_signing_keys_expires_at"), "gateway_signing_keys", ["expires_at"], unique=False)
    op.create_index(op.f("ix_gateway_signing_keys_is_active"), "gateway_signing_keys", ["is_active"], unique=False)
    op.create_index(op.f("ix_gateway_signing_keys_key_id"), "gateway_signing_keys", ["key_id"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_gateway_signing_keys_key_id"), table_name="gateway_signing_keys")
    op.drop_index(op.f("ix_gateway_signing_keys_is_active"), table_name="gateway_signing_keys")
    op.drop_index(op.f("ix_gateway_signing_keys_expires_at"), table_name="gateway_signing_keys")
    op.drop_index(op.f("ix_gateway_signing_keys_active_from"), table_name="gateway_signing_keys")
    op.drop_table("gateway_signing_keys")
    op.drop_index(op.f("ix_callback_dedup_keys_transaction_reference"), table_name="callback_dedup_keys")
    op.drop_index(op.f("ix_callback_dedup_keys_expires_at"), table_name="callback_dedup_keys")
    op.drop_index(op.f("ix_callback_dedup_keys_callback_id"), table_name="callback_dedup_keys")
    op.drop_table("callback_dedup_keys")
    op.drop_index(op.f("ix_payment_callbacks_verification_status"), table_name="payment_callbacks")
    op.drop_index(op.f("ix_payment_callbacks_transaction_reference"), table_name="payment_callbacks")
    op.drop_index(op.f("ix_payment_callbacks_payment_transaction_id"), table_name="payment_callbacks")
    op.drop_index(op.f("ix_payment_callbacks_payload_hash"), table_name="payment_callbacks")
    op.drop_index(op.f("ix_payment_callbacks_key_id"), table_name="payment_callbacks")
    op.drop_index(op.f("ix_payment_callbacks_duplicate_of_callback_id"), table_name="payment_callbacks")
    op.drop_table("payment_callbacks")
    op.drop_index(op.f("ix_payment_transactions_transaction_reference"), table_name="payment_transactions")
    op.drop_index(op.f("ix_payment_transactions_status"), table_name="payment_transactions")
    op.drop_index(op.f("ix_payment_transactions_order_id"), table_name="payment_transactions")
    op.drop_table("payment_transactions")
