"""Catalogue: categories, products, stock ledger (spec 03, architecture §5.2–5.3, §5.7)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import db
from core.models.base import TimestampMixin
from core.models.user import User

Money = Numeric(12, 2)


class Category(TimestampMixin, db.Model):  # type: ignore[name-defined,misc]
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())


class Product(TimestampMixin, db.Model):  # type: ignore[name-defined,misc]
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("cost_price >= 0", name="cost_non_negative"),
        CheckConstraint(
            "cost_price <= selling_price AND selling_price <= market_price", name="price_order"
        ),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("reorder_level >= 0", name="reorder_non_negative"),
        CheckConstraint("mp_round_mode IN ('primary', 'alternate')", name="mp_round_mode_valid"),
        Index("ix_products_name_lower", text("lower(name)")),
        Index("ix_products_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id"))
    unit: Mapped[str] = mapped_column(String(10), nullable=False, server_default="pcs")
    image_public_id: Mapped[str | None] = mapped_column(String(255))
    cost_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    market_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    mp_is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sp_is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    mp_round_mode: Mapped[str] = mapped_column(String(10), nullable=False, server_default="primary")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))

    category: Mapped[Category | None] = relationship(lazy="joined")
    updater: Mapped[User | None] = relationship(foreign_keys=[updated_by], lazy="joined")

    # SQLAlchemy bumps `version` on every UPDATE and refuses stale writes (spec 03 §6.6).
    __mapper_args__ = {"version_id_col": version}

    @property
    def low_stock(self) -> bool:
        return self.quantity <= self.reorder_level


class StockMovement(db.Model):  # type: ignore[name-defined,misc]
    """Ledger: every change to products.quantity has exactly one row here (OS-4)."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("change <> 0", name="change_non_zero"),
        CheckConstraint("quantity_after >= 0", name="quantity_after_non_negative"),
        CheckConstraint(
            "reason IN ('initial', 'restock', 'sale', 'adjustment', 'damage', 'correction')",
            name="reason_valid",
        ),
        Index("ix_stock_movements_product_id", "product_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"), nullable=False)
    change: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(20))
    reference_id: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(String(255))
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PricingSettings(db.Model):  # type: ignore[name-defined,misc]
    """Single row (id = 1) holding the owner's pricing rule numbers (spec 04)."""

    __tablename__ = "pricing_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    markup_low_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    markup_high_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    markup_threshold: Mapped[Decimal] = mapped_column(Money, nullable=False)
    small_mp_limit: Mapped[Decimal] = mapped_column(Money, nullable=False)
    small_mp_step: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    small_mp_alt_step: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    mp_step: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    mp_alt_step: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    sp_discount_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    sp_step: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
