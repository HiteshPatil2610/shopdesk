"""Local mirror of Clerk users (architecture §5.1). Clerk owns identity and passwords;
this table exists so orders/products/audit rows can reference a person by FK."""

from __future__ import annotations

from datetime import datetime
from typing import Final

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from core.db import db
from core.models.base import TimestampMixin

ROLES: Final = ("admin", "manager", "cashier")


class User(TimestampMixin, db.Model):  # type: ignore[name-defined,misc]
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'manager', 'cashier')", name="role_valid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    clerk_user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def display_name(self) -> str:
        return self.username or self.full_name

    def to_public(self) -> dict[str, object]:
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
        }


class WebhookEvent(db.Model):  # type: ignore[name-defined,misc]
    """Dedupe table for Clerk (svix) webhook deliveries."""

    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    svix_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
