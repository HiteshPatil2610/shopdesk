"""The ONLY code allowed to change products.quantity (hard rule H5, OS-4).

Spec 03 uses `apply_movement` for the initial stock; spec 07 adds sales and adjustments.
"""

from __future__ import annotations

from typing import Literal

from core.actor import ActorContext
from core.db import db
from core.errors import BusinessRuleError
from core.models import Product, StockMovement

Reason = Literal["initial", "restock", "sale", "adjustment", "damage", "correction"]


def apply_movement(
    product: Product,
    change: int,
    reason: Reason,
    actor: ActorContext,
    *,
    reference_type: str | None = None,
    reference_id: int | None = None,
    note: str | None = None,
) -> StockMovement:
    """Change quantity by `change` and write the ledger row in the caller's transaction."""
    if change == 0:
        raise ValueError("Stock movement must change the quantity")
    new_quantity = product.quantity + change
    if new_quantity < 0:
        raise BusinessRuleError(
            f"{product.code} would go below zero ({product.quantity} {change:+d})",
            code="NEGATIVE_STOCK",
        )
    product.quantity = new_quantity
    movement = StockMovement(
        product_id=product.id,
        change=change,
        quantity_after=new_quantity,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
        user_id=actor.user_id,
    )
    db.session.add(movement)
    return movement


def record_initial(product: Product, actor: ActorContext) -> StockMovement | None:
    """Ledger row for the opening stock of a product inserted with quantity already set."""
    if product.quantity <= 0:
        return None
    movement = StockMovement(
        product_id=product.id,
        change=product.quantity,
        quantity_after=product.quantity,
        reason="initial",
        user_id=actor.user_id,
    )
    db.session.add(movement)
    return movement
