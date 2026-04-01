"""moderation schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_0008"
down_revision = "20260328_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "moderation_reason_codes",
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_moderation_reason_codes_code"), "moderation_reason_codes", ["code"], unique=True)

    op.create_table(
        "moderation_queue",
        sa.Column("report_id", sa.String(length=36), nullable=True),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("target_user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("latest_reason_code", sa.String(length=60), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["latest_reason_code"], ["moderation_reason_codes.code"]),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_moderation_queue_priority"), "moderation_queue", ["priority"], unique=False)
    op.create_index(op.f("ix_moderation_queue_report_id"), "moderation_queue", ["report_id"], unique=False)
    op.create_index(op.f("ix_moderation_queue_status"), "moderation_queue", ["status"], unique=False)
    op.create_index(op.f("ix_moderation_queue_target_id"), "moderation_queue", ["target_id"], unique=False)
    op.create_index(op.f("ix_moderation_queue_target_type"), "moderation_queue", ["target_type"], unique=False)
    op.create_index(op.f("ix_moderation_queue_target_user_id"), "moderation_queue", ["target_user_id"], unique=False)

    op.create_table(
        "moderation_actions",
        sa.Column("moderation_item_id", sa.String(length=36), nullable=False),
        sa.Column("operator_user_id", sa.String(length=36), nullable=False),
        sa.Column("reason_code", sa.String(length=60), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("operator_notes", sa.Text(), nullable=False),
        sa.Column("from_status", sa.String(length=40), nullable=True),
        sa.Column("to_status", sa.String(length=40), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["moderation_item_id"], ["moderation_queue.id"]),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reason_code"], ["moderation_reason_codes.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_moderation_actions_moderation_item_id"), "moderation_actions", ["moderation_item_id"], unique=False)
    op.create_index(op.f("ix_moderation_actions_operator_user_id"), "moderation_actions", ["operator_user_id"], unique=False)
    op.create_index(op.f("ix_moderation_actions_outcome"), "moderation_actions", ["outcome"], unique=False)
    op.create_index(op.f("ix_moderation_actions_reason_code"), "moderation_actions", ["reason_code"], unique=False)

    op.create_table(
        "role_change_events",
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("target_user_id", sa.String(length=36), nullable=False),
        sa.Column("role_name", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_role_change_events_actor_user_id"), "role_change_events", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_role_change_events_status"), "role_change_events", ["status"], unique=False)
    op.create_index(op.f("ix_role_change_events_target_user_id"), "role_change_events", ["target_user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_role_change_events_target_user_id"), table_name="role_change_events")
    op.drop_index(op.f("ix_role_change_events_status"), table_name="role_change_events")
    op.drop_index(op.f("ix_role_change_events_actor_user_id"), table_name="role_change_events")
    op.drop_table("role_change_events")
    op.drop_index(op.f("ix_moderation_actions_reason_code"), table_name="moderation_actions")
    op.drop_index(op.f("ix_moderation_actions_outcome"), table_name="moderation_actions")
    op.drop_index(op.f("ix_moderation_actions_operator_user_id"), table_name="moderation_actions")
    op.drop_index(op.f("ix_moderation_actions_moderation_item_id"), table_name="moderation_actions")
    op.drop_table("moderation_actions")
    op.drop_index(op.f("ix_moderation_queue_target_user_id"), table_name="moderation_queue")
    op.drop_index(op.f("ix_moderation_queue_target_type"), table_name="moderation_queue")
    op.drop_index(op.f("ix_moderation_queue_target_id"), table_name="moderation_queue")
    op.drop_index(op.f("ix_moderation_queue_status"), table_name="moderation_queue")
    op.drop_index(op.f("ix_moderation_queue_report_id"), table_name="moderation_queue")
    op.drop_index(op.f("ix_moderation_queue_priority"), table_name="moderation_queue")
    op.drop_table("moderation_queue")
    op.drop_index(op.f("ix_moderation_reason_codes_code"), table_name="moderation_reason_codes")
    op.drop_table("moderation_reason_codes")
