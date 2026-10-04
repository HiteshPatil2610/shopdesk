"""The MP/SP formula (spec 04) — pure functions, Decimal only, no DB, no Flask (PE-1).

Owner's rules (2026-10-04):
  MP  = cost + 95% when cost < ₹500, cost + 90% when cost ≥ ₹500
        rounded UP — default to the next ₹50, alternative option to the next ₹100
        (MPs under ₹500 use smaller steps: ₹10, alternative ₹50)
  SP  = MP − 10%, rounded DOWN to the nearest ₹10
  and always cost ≤ SP ≤ MP (PE-2 / BR-2).

All the numbers live in PricingRules so the admin can tune them without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Literal

from core.money import q2, to_decimal

MpMode = Literal["primary", "alternate"]
HUNDRED = Decimal(100)


@dataclass(frozen=True)
class PricingRules:
    markup_low_pct: Decimal = Decimal("95")  # cost below the threshold
    markup_high_pct: Decimal = Decimal("90")  # cost at/above the threshold
    markup_threshold: Decimal = Decimal("500")
    small_mp_limit: Decimal = Decimal("500")  # raw MP below this uses the small steps
    small_mp_step: Decimal = Decimal("10")
    small_mp_alt_step: Decimal = Decimal("50")
    mp_step: Decimal = Decimal("50")
    mp_alt_step: Decimal = Decimal("100")
    sp_discount_pct: Decimal = Decimal("10")
    sp_step: Decimal = Decimal("10")


DEFAULT_RULES = PricingRules()


@dataclass(frozen=True)
class MpOption:
    mode: MpMode
    value: Decimal
    step: Decimal


@dataclass(frozen=True)
class PriceResult:
    raw_mp: Decimal
    market_price: Decimal
    selling_price: Decimal
    mp_mode: MpMode
    mp_options: tuple[MpOption, ...]
    markup_pct: Decimal
    explanation: str


def ceil_to(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return q2(value)
    return q2((value / step).to_integral_value(rounding=ROUND_CEILING) * step)


def floor_to(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return q2(value)
    return q2((value / step).to_integral_value(rounding=ROUND_FLOOR) * step)


def markup_for(cost: Decimal, rules: PricingRules = DEFAULT_RULES) -> Decimal:
    return rules.markup_low_pct if cost < rules.markup_threshold else rules.markup_high_pct


def raw_market_price(cost: Decimal, rules: PricingRules = DEFAULT_RULES) -> Decimal:
    return q2(cost * (1 + markup_for(cost, rules) / HUNDRED))


def mp_options(raw_mp: Decimal, rules: PricingRules = DEFAULT_RULES) -> tuple[MpOption, ...]:
    """Rounded-up choices for MP: primary (default) and, if different, the bigger alternate."""
    small = raw_mp < rules.small_mp_limit
    step = rules.small_mp_step if small else rules.mp_step
    alt_step = rules.small_mp_alt_step if small else rules.mp_alt_step
    primary = MpOption("primary", ceil_to(raw_mp, step), step)
    alternate = MpOption("alternate", ceil_to(raw_mp, alt_step), alt_step)
    return (primary,) if alternate.value == primary.value else (primary, alternate)


def pick_option(options: tuple[MpOption, ...], mode: MpMode) -> MpOption:
    for option in options:
        if option.mode == mode:
            return option
    return options[0]  # alternate equals primary → only one option exists


def selling_price_for(
    market_price: Decimal, cost: Decimal, rules: PricingRules = DEFAULT_RULES
) -> Decimal:
    """SP = MP − discount%, rounded DOWN to the step, clamped into [cost, MP] (PE-2)."""
    mp = to_decimal(market_price)
    sp = floor_to(mp * (1 - rules.sp_discount_pct / HUNDRED), rules.sp_step)
    if sp < cost:
        sp = min(mp, ceil_to(cost, rules.sp_step))
    if sp < cost:  # MP itself is below the step-rounded cost; fall back to the exact cost
        sp = q2(cost)
    return min(sp, q2(mp))


def calculate(
    cost_price: Decimal | str | int,
    rules: PricingRules = DEFAULT_RULES,
    mp_mode: MpMode = "primary",
) -> PriceResult:
    cost = q2(to_decimal(cost_price))
    if cost < 0:
        raise ValueError("Cost price can't be negative")
    raw = raw_market_price(cost, rules)
    options = mp_options(raw, rules)
    chosen = pick_option(options, mp_mode)
    mp = max(chosen.value, cost)
    sp = selling_price_for(mp, cost, rules)
    pct = markup_for(cost, rules)
    explanation = (
        f"{cost} + {_n(pct)}% = {raw} → up to ₹{_n(chosen.step)} = {mp}; "
        f"SP = {mp} − {_n(rules.sp_discount_pct)}% → down to ₹{_n(rules.sp_step)} = {sp}"
    )
    return PriceResult(
        raw_mp=raw,
        market_price=mp,
        selling_price=sp,
        mp_mode=chosen.mode,
        mp_options=options,
        markup_pct=pct,
        explanation=explanation,
    )


def _n(value: Decimal) -> str:
    """50.00 → "50", 2.5 → "2.5" (no scientific notation)."""
    return format(value.normalize(), "f")


def margin_pct(price: Decimal, cost: Decimal) -> Decimal | None:
    """Profit as % of the price (shown in the admin UI)."""
    if price <= 0:
        return None
    return q2((price - cost) / price * HUNDRED)
