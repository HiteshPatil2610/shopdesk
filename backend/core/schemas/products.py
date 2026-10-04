"""Product, category and pricing schemas (specs 03 + 04).

Money comes in as strings ("212.00") and is parsed to Decimal — floats are rejected (BR-1).
POS output uses PosProductOut, which has NO cost/margin fields at all (BR-12).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from core.money import q2, to_decimal

MAX_PRICE = Decimal("9999999.99")


def _parse_money(value: object) -> Decimal:
    if isinstance(value, float):
        raise ValueError('Send amounts as strings, e.g. "212.00"')
    if isinstance(value, str | int | Decimal):
        try:
            amount = q2(to_decimal(value))
        except (TypeError, ValueError) as exc:
            raise ValueError("Not a valid amount") from exc
        if amount < 0 or amount > MAX_PRICE:
            raise ValueError("Amount must be between 0 and 9,999,999.99")
        return amount
    raise ValueError("Not a valid amount")


MoneyIn = Annotated[Decimal, BeforeValidator(_parse_money)]
MpMode = Literal["primary", "alternate"]
Unit = Literal["pcs", "kg", "g", "l", "ml", "m", "box", "pack", "pair", "set", "dozen"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _blank_to_none(value: object) -> object:
    return None if isinstance(value, str) and not value.strip() else value


OptStr = Annotated[str | None, BeforeValidator(_blank_to_none)]


class CategoryCreate(_Strict):
    name: str = Field(min_length=2, max_length=80)


class ProductCreate(_Strict):
    name: str = Field(min_length=2, max_length=150)
    category_id: Annotated[int | None, BeforeValidator(_blank_to_none)] = None
    unit: Unit = "pcs"
    barcode: OptStr = Field(default=None, max_length=64)
    description: OptStr = Field(default=None, max_length=2000)
    quantity: int = Field(ge=0, le=1_000_000)
    reorder_level: int = Field(default=5, ge=0, le=1_000_000)
    cost_price: MoneyIn
    mp_round_mode: MpMode = "primary"
    # Optional manual prices: when given, they're kept as typed and flagged manual.
    market_price: Annotated[MoneyIn | None, BeforeValidator(_blank_to_none)] = None
    selling_price: Annotated[MoneyIn | None, BeforeValidator(_blank_to_none)] = None

    @field_validator("barcode")
    @classmethod
    def _barcode_chars(cls, v: str | None) -> str | None:
        if v and not v.replace("-", "").isalnum():
            raise ValueError("Barcode may contain letters, numbers and dashes only")
        return v


class ProductUpdate(_Strict):
    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=2, max_length=150)
    category_id: int | None = None
    unit: Unit | None = None
    barcode: OptStr = Field(default=None, max_length=64)
    description: OptStr = Field(default=None, max_length=2000)
    reorder_level: int | None = Field(default=None, ge=0, le=1_000_000)
    cost_price: MoneyIn | None = None
    market_price: MoneyIn | None = None
    selling_price: MoneyIn | None = None
    mp_round_mode: MpMode | None = None
    mp_is_manual: bool | None = None
    sp_is_manual: bool | None = None
    quantity: int | None = None  # rejected with a helpful message (PR-3)
    clear_category: bool = False
    clear_barcode: bool = False


SortKey = Literal["name", "-name", "code", "-updated_at", "quantity", "-quantity", "market_price"]


class ProductListQuery(_Strict):
    search: OptStr = Field(default=None, max_length=100)
    category_id: int | None = None
    low_stock: bool = False
    include_inactive: bool = False
    sort: SortKey = "name"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class PricingSettingsIn(_Strict):
    markup_low_pct: MoneyIn = Field(le=Decimal("500"))
    markup_high_pct: MoneyIn = Field(le=Decimal("500"))
    markup_threshold: MoneyIn
    small_mp_limit: MoneyIn
    small_mp_step: MoneyIn
    small_mp_alt_step: MoneyIn
    mp_step: MoneyIn
    mp_alt_step: MoneyIn
    sp_discount_pct: MoneyIn = Field(le=Decimal("90"))
    sp_step: MoneyIn

    @field_validator("small_mp_step", "small_mp_alt_step", "mp_step", "mp_alt_step", "sp_step")
    @classmethod
    def _positive_step(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Rounding steps must be greater than 0")
        return v


class PricingPreviewIn(_Strict):
    cost_price: MoneyIn
    mp_round_mode: MpMode = "primary"
    # A manually typed MP: the preview then returns the SP that follows from it.
    market_price: Annotated[MoneyIn | None, BeforeValidator(_blank_to_none)] = None
    settings: PricingSettingsIn | None = None  # preview unsaved settings on the settings page
