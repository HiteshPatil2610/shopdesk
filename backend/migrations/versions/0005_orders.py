"""orders, order items (price snapshots), daily invoice counters — spec 07

Revision ID: 0005_orders
Revises: 0004_sp_avoid_ten
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_orders"
down_revision = "0004_sp_avoid_ten"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(12, 2)


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("order_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(15), nullable=False),
        sa.Column("customer_name", sa.String(120), nullable=False),
        sa.Column("customer_phone", sa.String(20)),
        sa.Column("cashier_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("discount_applied", sa.Boolean(), nullable=False),
        sa.Column("payment_mode", sa.String(10)),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("subtotal_mp", MONEY, nullable=False),
        sa.Column("discount_amount", MONEY, nullable=False),
        sa.Column("total_amount", MONEY, nullable=False),
        sa.Column("total_cost", MONEY, nullable=False),
        sa.Column("reject_reason", sa.String(255)),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("order_number", name="uq_orders_order_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_orders_idempotency_key"),
        sa.CheckConstraint("status IN ('confirmed', 'rejected')", name="status_valid"),
        sa.CheckConstraint(
            "payment_mode IS NULL OR payment_mode IN ('cash', 'upi', 'card')",
            name="payment_mode_valid",
        ),
    )
    op.create_index("ix_orders_status_created_at", "orders", ["status", "created_at"])
    op.create_index("ix_orders_cashier_id", "orders", ["cashier_id", "created_at"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "order_id",
            sa.BigInteger(),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("product_code", sa.String(20), nullable=False),
        sa.Column("product_name", sa.String(150), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost", MONEY, nullable=False),
        sa.Column("unit_mp", MONEY, nullable=False),
        sa.Column("unit_sp", MONEY, nullable=False),
        sa.Column("unit_price_charged", MONEY, nullable=False),
        sa.Column("line_total", MONEY, nullable=False),
        sa.CheckConstraint("quantity > 0", name="quantity_positive"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])

    op.create_table(
        "daily_counters",
        sa.Column("counter_date", sa.Date(), primary_key=True),
        sa.Column("kind", sa.String(10), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("daily_counters")
    op.drop_table("order_items")
    op.drop_table("orders")
