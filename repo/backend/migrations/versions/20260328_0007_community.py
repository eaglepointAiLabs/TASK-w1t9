"""community schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_0007"
down_revision = "20260328_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "posts",
        sa.Column("author_user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("target_dish_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_dish_id"], ["dishes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_posts_author_user_id"), "posts", ["author_user_id"], unique=False)
    op.create_index(op.f("ix_posts_target_dish_id"), "posts", ["target_dish_id"], unique=False)

    op.create_table(
        "comments",
        sa.Column("author_user_id", sa.String(length=36), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_comments_author_user_id"), "comments", ["author_user_id"], unique=False)
    op.create_index(op.f("ix_comments_target_id"), "comments", ["target_id"], unique=False)
    op.create_index(op.f("ix_comments_target_type"), "comments", ["target_type"], unique=False)

    op.create_table(
        "likes",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "target_type", "target_id", name="uq_like_target"),
    )
    op.create_index(op.f("ix_likes_target_id"), "likes", ["target_id"], unique=False)
    op.create_index(op.f("ix_likes_target_type"), "likes", ["target_type"], unique=False)
    op.create_index(op.f("ix_likes_user_id"), "likes", ["user_id"], unique=False)

    op.create_table(
        "favorites",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "target_type", "target_id", name="uq_favorite_target"),
    )
    op.create_index(op.f("ix_favorites_target_id"), "favorites", ["target_id"], unique=False)
    op.create_index(op.f("ix_favorites_target_type"), "favorites", ["target_type"], unique=False)
    op.create_index(op.f("ix_favorites_user_id"), "favorites", ["user_id"], unique=False)

    op.create_table(
        "reports",
        sa.Column("reporter_user_id", sa.String(length=36), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("reason_code", sa.String(length=60), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_reporter_user_id"), "reports", ["reporter_user_id"], unique=False)
    op.create_index(op.f("ix_reports_status"), "reports", ["status"], unique=False)
    op.create_index(op.f("ix_reports_target_id"), "reports", ["target_id"], unique=False)
    op.create_index(op.f("ix_reports_target_type"), "reports", ["target_type"], unique=False)

    op.create_table(
        "user_blocks",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("blocked_user_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["blocked_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "blocked_user_id", name="uq_user_block"),
    )
    op.create_index(op.f("ix_user_blocks_blocked_user_id"), "user_blocks", ["blocked_user_id"], unique=False)
    op.create_index(op.f("ix_user_blocks_user_id"), "user_blocks", ["user_id"], unique=False)

    op.create_table(
        "cooldown_events",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cooldown_events_action_type"), "cooldown_events", ["action_type"], unique=False)
    op.create_index(op.f("ix_cooldown_events_expires_at"), "cooldown_events", ["expires_at"], unique=False)
    op.create_index(op.f("ix_cooldown_events_target_id"), "cooldown_events", ["target_id"], unique=False)
    op.create_index(op.f("ix_cooldown_events_target_type"), "cooldown_events", ["target_type"], unique=False)
    op.create_index(op.f("ix_cooldown_events_user_id"), "cooldown_events", ["user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_cooldown_events_user_id"), table_name="cooldown_events")
    op.drop_index(op.f("ix_cooldown_events_target_type"), table_name="cooldown_events")
    op.drop_index(op.f("ix_cooldown_events_target_id"), table_name="cooldown_events")
    op.drop_index(op.f("ix_cooldown_events_expires_at"), table_name="cooldown_events")
    op.drop_index(op.f("ix_cooldown_events_action_type"), table_name="cooldown_events")
    op.drop_table("cooldown_events")
    op.drop_index(op.f("ix_user_blocks_user_id"), table_name="user_blocks")
    op.drop_index(op.f("ix_user_blocks_blocked_user_id"), table_name="user_blocks")
    op.drop_table("user_blocks")
    op.drop_index(op.f("ix_reports_target_type"), table_name="reports")
    op.drop_index(op.f("ix_reports_target_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_status"), table_name="reports")
    op.drop_index(op.f("ix_reports_reporter_user_id"), table_name="reports")
    op.drop_table("reports")
    op.drop_index(op.f("ix_favorites_user_id"), table_name="favorites")
    op.drop_index(op.f("ix_favorites_target_type"), table_name="favorites")
    op.drop_index(op.f("ix_favorites_target_id"), table_name="favorites")
    op.drop_table("favorites")
    op.drop_index(op.f("ix_likes_user_id"), table_name="likes")
    op.drop_index(op.f("ix_likes_target_type"), table_name="likes")
    op.drop_index(op.f("ix_likes_target_id"), table_name="likes")
    op.drop_table("likes")
    op.drop_index(op.f("ix_comments_target_type"), table_name="comments")
    op.drop_index(op.f("ix_comments_target_id"), table_name="comments")
    op.drop_index(op.f("ix_comments_author_user_id"), table_name="comments")
    op.drop_table("comments")
    op.drop_index(op.f("ix_posts_target_dish_id"), table_name="posts")
    op.drop_index(op.f("ix_posts_author_user_id"), table_name="posts")
    op.drop_table("posts")
