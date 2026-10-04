"""Read-only POS quote contracts; browser prices are deliberately ignored."""

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
