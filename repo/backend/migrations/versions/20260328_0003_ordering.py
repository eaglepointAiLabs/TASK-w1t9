"""ordering schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_0003"
down_revision = "20260328_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("dishes", sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "carts",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_carts_status"), "carts", ["status"], unique=False)
    op.create_index(op.f("ix_carts_user_id"), "carts", ["user_id"], unique=False)

    op.create_table(
        "cart_items",
        sa.Column("cart_id", sa.String(length=36), nullable=False),
        sa.Column("dish_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("selected_options_json", sa.Text(), nullable=False),
        sa.Column("unit_base_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_options_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("pricing_breakdown_json", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"]),
        sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cart_items_cart_id"), "cart_items", ["cart_id"], unique=False)
    op.create_index(op.f("ix_cart_items_dish_id"), "cart_items", ["dish_id"], unique=False)

    op.create_table(
        "orders",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("cart_id", sa.String(length=36), nullable=True),
        sa.Column("checkout_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("subtotal_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "checkout_key", name="uq_order_checkout_key"),
    )
    op.create_index(op.f("ix_orders_cart_id"), "orders", ["cart_id"], unique=False)
    op.create_index(op.f("ix_orders_status"), "orders", ["status"], unique=False)
    op.create_index(op.f("ix_orders_user_id"), "orders", ["user_id"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("dish_id", sa.String(length=36), nullable=False),
        sa.Column("dish_name", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("selected_options_json", sa.Text(), nullable=False),
        sa.Column("unit_base_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_options_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("pricing_breakdown_json", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_items_dish_id"), "order_items", ["dish_id"], unique=False)
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"], unique=False)

    op.create_table(
        "order_status_history",
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("from_status", sa.String(length=40), nullable=True),
        sa.Column("to_status", sa.String(length=40), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_status_history_order_id"), "order_status_history", ["order_id"], unique=False)

    op.create_table(
        "inventory_reservations",
        sa.Column("order_id", sa.String(length=36), nullable=True),
        sa.Column("dish_id", sa.String(length=36), nullable=False),
        sa.Column("checkout_key", sa.String(length=120), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_reservations_checkout_key"), "inventory_reservations", ["checkout_key"], unique=False)
    op.create_index(op.f("ix_inventory_reservations_dish_id"), "inventory_reservations", ["dish_id"], unique=False)
    op.create_index(op.f("ix_inventory_reservations_order_id"), "inventory_reservations", ["order_id"], unique=False)
    op.create_index(op.f("ix_inventory_reservations_status"), "inventory_reservations", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_inventory_reservations_status"), table_name="inventory_reservations")
    op.drop_index(op.f("ix_inventory_reservations_order_id"), table_name="inventory_reservations")
    op.drop_index(op.f("ix_inventory_reservations_dish_id"), table_name="inventory_reservations")
    op.drop_index(op.f("ix_inventory_reservations_checkout_key"), table_name="inventory_reservations")
    op.drop_table("inventory_reservations")
    op.drop_index(op.f("ix_order_status_history_order_id"), table_name="order_status_history")
    op.drop_table("order_status_history")
    op.drop_index(op.f("ix_order_items_order_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_dish_id"), table_name="order_items")
    op.drop_table("order_items")
    op.drop_index(op.f("ix_orders_user_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_status"), table_name="orders")
    op.drop_index(op.f("ix_orders_cart_id"), table_name="orders")
    op.drop_table("orders")
    op.drop_index(op.f("ix_cart_items_dish_id"), table_name="cart_items")
    op.drop_index(op.f("ix_cart_items_cart_id"), table_name="cart_items")
    op.drop_table("cart_items")
    op.drop_index(op.f("ix_carts_user_id"), table_name="carts")
    op.drop_index(op.f("ix_carts_status"), table_name="carts")
    op.drop_table("carts")
    op.drop_column("dishes", "stock_quantity")
