"""catalogue (categories, products, stock ledger) + pricing settings — specs 03 + 04

Revision ID: 0003_catalog_pricing
Revises: 0002_users_audit
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_catalog_pricing"
down_revision = "0002_users_audit"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(12, 2)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )

    # PR-1: product codes come from a sequence and are never reused.
    op.execute("CREATE SEQUENCE product_code_seq START 1")

    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("barcode", sa.String(64)),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category_id", sa.BigInteger(), sa.ForeignKey("categories.id")),
        sa.Column("unit", sa.String(10), server_default="pcs", nullable=False),
        sa.Column("image_public_id", sa.String(255)),
        sa.Column("cost_price", MONEY, nullable=False),
        sa.Column("market_price", MONEY, nullable=False),
        sa.Column("selling_price", MONEY, nullable=False),
        sa.Column("mp_is_manual", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("sp_is_manual", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("mp_round_mode", sa.String(10), server_default="primary", nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reorder_level", sa.Integer(), server_default="5", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("updated_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_products_code"),
        sa.UniqueConstraint("barcode", name="uq_products_barcode"),
        sa.CheckConstraint("cost_price >= 0", name="cost_non_negative"),
        sa.CheckConstraint(
            "cost_price <= selling_price AND selling_price <= market_price", name="price_order"
        ),
        sa.CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        sa.CheckConstraint("reorder_level >= 0", name="reorder_non_negative"),
        sa.CheckConstraint(
            "mp_round_mode IN ('primary', 'alternate')", name="mp_round_mode_valid"
        ),
    )
    op.create_index("ix_products_name_lower", "products", [sa.text("lower(name)")])
    op.create_index("ix_products_is_active", "products", ["is_active"])

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("change", sa.Integer(), nullable=False),
        sa.Column("quantity_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("reference_type", sa.String(20)),
        sa.Column("reference_id", sa.BigInteger()),
        sa.Column("note", sa.String(255)),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("change <> 0", name="change_non_zero"),
        sa.CheckConstraint("quantity_after >= 0", name="quantity_after_non_negative"),
        sa.CheckConstraint(
            "reason IN ('initial', 'restock', 'sale', 'adjustment', 'damage', 'correction')",
            name="reason_valid",
        ),
    )
    op.create_index(
        "ix_stock_movements_product_id", "stock_movements", ["product_id", "created_at"]
    )

    pricing = op.create_table(
        "pricing_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("markup_low_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("markup_high_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("markup_threshold", MONEY, nullable=False),
        sa.Column("small_mp_limit", MONEY, nullable=False),
        sa.Column("small_mp_step", sa.Numeric(8, 2), nullable=False),
        sa.Column("small_mp_alt_step", sa.Numeric(8, 2), nullable=False),
        sa.Column("mp_step", sa.Numeric(8, 2), nullable=False),
        sa.Column("mp_alt_step", sa.Numeric(8, 2), nullable=False),
        sa.Column("sp_discount_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("sp_step", sa.Numeric(8, 2), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("id = 1", name="single_row"),
    )
    # Owner's rules (2026-10-04): +95% under ₹500 cost, +90% from ₹500; MP up to ₹50 (alt ₹100),
    # small MPs up to ₹10 (alt ₹50); SP = MP − 10% down to ₹10.
    op.bulk_insert(
        pricing,
        [
            {
                "id": 1,
                "markup_low_pct": 95,
                "markup_high_pct": 90,
                "markup_threshold": 500,
                "small_mp_limit": 500,
                "small_mp_step": 10,
                "small_mp_alt_step": 50,
                "mp_step": 50,
                "mp_alt_step": 100,
                "sp_discount_pct": 10,
                "sp_step": 10,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("pricing_settings")
    op.drop_table("stock_movements")
    op.drop_table("products")
    op.execute("DROP SEQUENCE IF EXISTS product_code_seq")
    op.drop_table("categories")
