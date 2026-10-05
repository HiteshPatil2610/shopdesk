"""The catalogue accepts pieces only, including direct API requests."""

import pytest
from pydantic import ValidationError

from core.schemas.products import ProductCreate, ProductUpdate


def test_new_products_default_to_pieces() -> None:
    product = ProductCreate(name="Bottle", cost_price="100", quantity=20)
    assert product.unit == "pcs"
    assert ProductUpdate(version=1, unit="pcs").unit == "pcs"


@pytest.mark.parametrize("unit", ["kg", "g", "l", "ml", "m", "box", "pack", "pair", "set", "dozen"])
def test_other_units_are_rejected_on_create_and_update(unit: str) -> None:
    with pytest.raises(ValidationError):
        ProductCreate(name="Bottle", cost_price="100", quantity=20, unit=unit)
    with pytest.raises(ValidationError):
        ProductUpdate(version=1, unit=unit)
