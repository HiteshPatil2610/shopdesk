"""Orders (confirmed or rejected), their lines, and the per-day invoice counter (spec 07)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import db
from core.models.user import User

Money = Numeric(12, 2)


class Order(db.Model):  # type: ignore[name-defined,misc]
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("status IN ('confirmed', 'rejected')", name="status_valid"),
        CheckConstraint(
            "payment_mode IS NULL OR payment_mode IN ('cash', 'upi', 'card')",
            name="payment_mode_valid",
        ),
        Index("ix_orders_status_created_at", "status", "created_at"),
        Index("ix_orders_cashier_id", "cashier_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(15), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_phone: Mapped[str | None] = mapped_column(String(20))
    cashier_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    discount_applied: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payment_mode: Mapped[str | None] = mapped_column(String(10))
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal_mp: Mapped[Decimal] = mapped_column(Money, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Money, nullable=False)
    reject_reason: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    cashier: Mapped[User] = relationship(lazy="joined")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", lazy="selectin", order_by="OrderItem.id"
    )


class OrderItem(db.Model):  # type: ignore[name-defined,misc]
    """One line, with prices copied at sale time (BR-6) so history never changes."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"), nullable=False)
    product_code: Mapped[str] = mapped_column(String(20), nullable=False)
    product_name: Mapped[str] = mapped_column(String(150), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Money, nullable=False)
    unit_mp: Mapped[Decimal] = mapped_column(Money, nullable=False)
    unit_sp: Mapped[Decimal] = mapped_column(Money, nullable=False)
    unit_price_charged: Mapped[Decimal] = mapped_column(Money, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Money, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")


class DailyCounter(db.Model):  # type: ignore[name-defined,misc]
    """Per-day invoice/reject numbering (OS-1, OS-2)."""

    __tablename__ = "daily_counters"

    counter_date: Mapped[date] = mapped_column(Date, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)
