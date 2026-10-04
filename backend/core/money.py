"""Money helpers. Money is Decimal everywhere (BR-1) — floats are rejected outright."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWO_PLACES = Decimal("0.01")

MoneyInput = str | int | Decimal


def to_decimal(value: MoneyInput) -> Decimal:
    """Convert a str/int/Decimal to Decimal. Raises TypeError for float/bool, ValueError for junk."""
    if isinstance(value, bool | float):
        raise TypeError("Money must not be a float or bool; pass a string or Decimal")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, str):
        try:
            result = Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValueError(f"Not a valid amount: {value!r}") from exc
    else:
        raise TypeError(f"Unsupported money type: {type(value).__name__}")
    if not result.is_finite():
        raise ValueError("Amount must be a finite number")
    return result


def q2(value: MoneyInput) -> Decimal:
    """Round to 2 decimal places, half-up (₹2.345 → ₹2.35)."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def money_str(value: MoneyInput) -> str:
    """Format for JSON responses: always a string with 2 decimals."""
    return format(q2(value), "f")
