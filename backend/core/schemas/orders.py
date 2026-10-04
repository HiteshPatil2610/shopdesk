"""Read-only POS quote contracts; browser prices are deliberately ignored."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuoteItem(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=20)
    qty: int = Field(strict=True, ge=1, le=10_000)

    @field_validator("code")
    @classmethod
    def _canonical_code(cls, v: str) -> str:
        return v.upper()  # codes are stored upper-case (P00042); lookup is case-insensitive too


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    discount_applied: bool = Field(strict=True)
    items: list[QuoteItem] = Field(max_length=100)


class QuoteLine(BaseModel):
    code: str
    name: str | None = None
    thumb_url: str | None = None
    qty: int
    available: int
    unit_mp: str
    unit_sp: str
    unit_price: str
    line_total: str
    status: Literal["ok", "not_found", "inactive", "insufficient_stock"]


class QuoteResponse(BaseModel):
    discount_applied: bool
    lines: list[QuoteLine]
    item_count: int
    subtotal_mp: str
    discount_amount: str
    total: str
    can_confirm: bool


# --- confirm / reject (spec 07) --------------------------------------------------------

PHONE_RE = r"^[6-9]\d{9}$"


class ConfirmRequest(BaseModel):
    """Only codes, quantities and the discount flag — prices are always taken from the DB."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    idempotency_key: uuid.UUID
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str | None = Field(default=None, pattern=PHONE_RE)
    payment_mode: Literal["cash", "upi", "card"] = "cash"
    discount_applied: bool = Field(strict=True)
    items: list[QuoteItem] = Field(min_length=1, max_length=100)

    @field_validator("customer_phone", mode="before")
    @classmethod
    def _blank_phone(cls, v: object) -> object:
        return None if isinstance(v, str) and not v.strip() else v


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    idempotency_key: uuid.UUID
    customer_name: str | None = Field(default=None, max_length=120)
    discount_applied: bool = False
    items: list[QuoteItem] = Field(default_factory=list, max_length=100)
    reason: str | None = Field(default=None, max_length=255)


class StockAdjustRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    type: Literal["restock", "damage", "correction"]
    qty: int = Field(strict=True, ge=-1_000_000, le=1_000_000)
    note: str | None = Field(default=None, max_length=255)

    @field_validator("note")
    @classmethod
    def _blank_note(cls, v: str | None) -> str | None:
        return v or None


class OrderListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)
    from_at: datetime | None = Field(default=None, alias="from")
    to_at: datetime | None = Field(default=None, alias="to")
    status: Literal["confirmed", "rejected"] | None = None
    cashier_id: int | None = Field(default=None, ge=1)
    q: str | None = Field(default=None, max_length=100)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)

    @field_validator("from_at", "to_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value

    @field_validator("q", "status", mode="before")
    @classmethod
    def _blank(cls, v: object) -> object:
        return None if isinstance(v, str) and not v.strip() else v
