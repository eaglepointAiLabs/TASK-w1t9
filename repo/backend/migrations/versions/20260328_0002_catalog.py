"""catalog schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_0002"
down_revision = "20260328_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dish_categories",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_dish_categories_name"), "dish_categories", ["name"], unique=True)
    op.create_index(op.f("ix_dish_categories_slug"), "dish_categories", ["slug"], unique=True)

    op.create_table(
        "dish_tags",
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_dish_tags_name"), "dish_tags", ["name"], unique=True)
    op.create_index(op.f("ix_dish_tags_slug"), "dish_tags", ["slug"], unique=True)

    op.create_table(
        "dishes",
        sa.Column("category_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("base_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("is_sold_out", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["dish_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_dishes_archived_at"), "dishes", ["archived_at"], unique=False)
    op.create_index(op.f("ix_dishes_category_id"), "dishes", ["category_id"], unique=False)
    op.create_index(op.f("ix_dishes_is_published"), "dishes", ["is_published"], unique=False)
    op.create_index(op.f("ix_dishes_is_sold_out"), "dishes", ["is_sold_out"], unique=False)
    op.create_index(op.f("ix_dishes_name"), "dishes", ["name"], unique=False)
    op.create_index(op.f("ix_dishes_slug"), "dishes", ["slug"], unique=True)

    op.create_table(
        "dish_tag_map",
        sa.Column("dish_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["dish_tags.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dish_id", "tag_id", name="uq_dish_tag"),
    )

    op.create_table(
        "dish_availability_windows",
        sa.Column("dish_id", sa.String(length=36), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dish_availability_windows_day_of_week"), "dish_availability_windows", ["day_of_week"], unique=False)
    op.create_index(op.f("ix_dish_availability_windows_dish_id"), "dish_availability_windows", ["dish_id"], unique=False)

    op.create_table(
        "dish_options",
        sa.Column("dish_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("display_type", sa.String(length=40), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dish_options_dish_id"), "dish_options", ["dish_id"], unique=False)

    op.create_table(
        "dish_option_values",
        sa.Column("option_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("value_code", sa.String(length=80), nullable=False),
        sa.Column("price_delta", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["option_id"], ["dish_options.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dish_option_values_option_id"), "dish_option_values", ["option_id"], unique=False)

    op.create_table(
        "dish_option_rules",
        sa.Column("option_id", sa.String(length=36), nullable=False),
        sa.Column("rule_type", sa.String(length=40), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("min_select", sa.Integer(), nullable=False),
        sa.Column("max_select", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["option_id"], ["dish_options.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dish_option_rules_option_id"), "dish_option_rules", ["option_id"], unique=False)

    op.create_table(
        "dish_images",
        sa.Column("dish_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("alt_text", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dish_images_dish_id"), "dish_images", ["dish_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_dish_images_dish_id"), table_name="dish_images")
    op.drop_table("dish_images")
    op.drop_index(op.f("ix_dish_option_rules_option_id"), table_name="dish_option_rules")
    op.drop_table("dish_option_rules")
    op.drop_index(op.f("ix_dish_option_values_option_id"), table_name="dish_option_values")
    op.drop_table("dish_option_values")
    op.drop_index(op.f("ix_dish_options_dish_id"), table_name="dish_options")
    op.drop_table("dish_options")
    op.drop_index(op.f("ix_dish_availability_windows_dish_id"), table_name="dish_availability_windows")
    op.drop_index(op.f("ix_dish_availability_windows_day_of_week"), table_name="dish_availability_windows")
    op.drop_table("dish_availability_windows")
    op.drop_table("dish_tag_map")
    op.drop_index(op.f("ix_dishes_slug"), table_name="dishes")
    op.drop_index(op.f("ix_dishes_name"), table_name="dishes")
    op.drop_index(op.f("ix_dishes_is_sold_out"), table_name="dishes")
    op.drop_index(op.f("ix_dishes_is_published"), table_name="dishes")
    op.drop_index(op.f("ix_dishes_category_id"), table_name="dishes")
    op.drop_index(op.f("ix_dishes_archived_at"), table_name="dishes")
    op.drop_table("dishes")
    op.drop_index(op.f("ix_dish_tags_slug"), table_name="dish_tags")
    op.drop_index(op.f("ix_dish_tags_name"), table_name="dish_tags")
    op.drop_table("dish_tags")
    op.drop_index(op.f("ix_dish_categories_slug"), table_name="dish_categories")
    op.drop_index(op.f("ix_dish_categories_name"), table_name="dish_categories")
    op.drop_table("dish_categories")
