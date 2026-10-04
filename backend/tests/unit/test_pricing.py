"""The owner's examples are the spec (spec 04 §5). Change these together with core/pricing.py."""

import random
from decimal import Decimal

import pytest

from core.pricing import (
    PricingRules,
    calculate,
    ceil_to,
    floor_to,
    mp_options,
    selling_price_for,
)

D = Decimal


# --- The owner's own examples --------------------------------------------------------


@pytest.mark.parametrize(("raw", "expected"), [("1243", "1250"), ("1412", "1450")])
def test_mp_rounds_up_to_next_50(raw, expected):
    assert mp_options(D(raw))[0].value == D(expected)


def test_mp_offers_bigger_round_off_option():
    options = mp_options(D("1412"))
    assert [(o.mode, o.value) for o in options] == [
        ("primary", D("1450.00")),
        ("alternate", D("1500.00")),
    ]


def test_single_option_when_both_roundings_agree():
    # 1460 → next 50 is 1500 and next 100 is 1500 → only one choice is offered
    assert [o.value for o in mp_options(D("1460"))] == [D("1500.00")]


@pytest.mark.parametrize(("raw_sp", "expected"), [("1212", "1210"), ("1293", "1290")])
def test_sp_rounds_down_to_closest_lower_ten(raw_sp, expected):
    # Owner's rule: "closest lower number with 0 at the end". (Their 1212 example said 1200;
    # set sp_step=100 if hundreds were meant.) Discount 0% isolates the rounding.
    no_discount = PricingRules(sp_discount_pct=D("0"))
    assert selling_price_for(D(raw_sp), D("1"), no_discount) == D(expected)


def test_sp_is_mp_minus_10_percent():
    assert selling_price_for(D("1450"), D("743")) == D("1300.00")  # 1305 → 1300


@pytest.mark.parametrize(
    ("cost", "markup"),
    [("100", D("95")), ("499.99", D("95")), ("500", D("90")), ("1000", D("90"))],
)
def test_markup_switches_at_500(cost, markup):
    assert calculate(cost).markup_pct == markup


# --- Worked examples table (spec 04 §5) -----------------------------------------------

EXAMPLES = [
    # cost,   raw MP,    MP primary, MP alternate, SP (from primary)
    ("212", "413.40", "420.00", "450.00", "370.00"),
    ("650", "1235.00", "1250.00", "1300.00", "1120.00"),
    ("743", "1411.70", "1450.00", "1500.00", "1300.00"),
    ("500", "950.00", "950.00", "1000.00", "850.00"),
    ("499", "973.05", "1000.00", None, "900.00"),
    ("20", "39.00", "40.00", "50.00", "30.00"),
    ("0", "0.00", "0.00", None, "0.00"),
]


@pytest.mark.parametrize(("cost", "raw", "mp", "alt", "sp"), EXAMPLES)
def test_worked_examples(cost, raw, mp, alt, sp):
    result = calculate(cost)
    assert result.raw_mp == D(raw)
    assert result.market_price == D(mp)
    assert result.selling_price == D(sp)
    values = [o.value for o in result.mp_options]
    assert values == ([D(mp), D(alt)] if alt else [D(mp)])


def test_alternate_mode_drives_sp():
    result = calculate("743", mp_mode="alternate")
    assert result.market_price == D("1500.00")
    assert result.selling_price == D("1350.00")


def test_alternate_falls_back_to_primary_when_only_one_option():
    assert calculate("499", mp_mode="alternate").market_price == D("1000.00")


# --- Invariants -----------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["primary", "alternate"])
def test_cost_le_sp_le_mp_for_random_costs(mode):
    rng = random.Random(2026)
    for _ in range(5000):
        cost = D(rng.randint(0, 10_000_000)) / 100
        r = calculate(cost, mp_mode=mode)
        assert cost <= r.selling_price <= r.market_price, (cost, r)


def test_invariant_holds_with_odd_settings():
    rules = PricingRules(markup_low_pct=D("1"), markup_high_pct=D("0"), sp_discount_pct=D("50"))
    rng = random.Random(7)
    for _ in range(2000):
        cost = D(rng.randint(0, 500_000)) / 100
        r = calculate(cost, rules)
        assert cost <= r.selling_price <= r.market_price


def test_rounding_helpers():
    assert ceil_to(D("1250"), D("50")) == D("1250.00")
    assert ceil_to(D("1250.01"), D("50")) == D("1300.00")
    assert floor_to(D("1299.99"), D("10")) == D("1290.00")


def test_negative_cost_rejected():
    with pytest.raises(ValueError):
        calculate("-1")


def test_float_cost_rejected():
    with pytest.raises(TypeError):
        calculate(10.5)  # type: ignore[arg-type]


def test_explanation_is_human_readable():
    assert "1235.00 → up to ₹50 = 1250.00" in calculate("650").explanation
