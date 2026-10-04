from decimal import Decimal

import pytest

from core.money import money_str, q2, to_decimal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2.345", Decimal("2.35")),
        ("2.344", Decimal("2.34")),
        ("0.005", Decimal("0.01")),
        ("10", Decimal("10.00")),
        (7, Decimal("7.00")),
        (Decimal("296.80"), Decimal("296.80")),
    ],
)
def test_q2_rounds_half_up(value, expected):
    assert q2(value) == expected


@pytest.mark.parametrize("bad", [0.1, 1.0, True, False])
def test_floats_and_bools_are_rejected(bad):
    with pytest.raises(TypeError):
        to_decimal(bad)


@pytest.mark.parametrize("bad", ["abc", "", "NaN", "Infinity", "1,000"])
def test_invalid_strings_are_rejected(bad):
    with pytest.raises(ValueError):
        to_decimal(bad)


def test_to_decimal_accepts_strings_and_strips_spaces():
    assert to_decimal(" 0.1 ") == Decimal("0.1")


def test_money_str_always_has_two_decimals():
    assert money_str("300") == "300.00"
    assert money_str(Decimal("2.5")) == "2.50"
