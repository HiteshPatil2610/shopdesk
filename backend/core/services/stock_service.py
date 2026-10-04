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


# --- admin stock adjustments & ledger (spec 07) -----------------------------------------

ADJUST_REASONS: dict[str, Reason] = {
    "restock": "restock",
    "damage": "damage",
    "correction": "correction",
}


def adjust(product_id: int, kind: str, qty: int, note: str | None, actor: ActorContext) -> Product:
    """Restock (+qty), damage (-qty) or correction (signed). Row is locked; result must be >= 0.

    OS-3: damage and correction need a note so the ledger explains every change.
    """
    from sqlalchemy import select

    from core.db import transaction
    from core.errors import NotFoundError, ValidationError
    from core.services import audit_service

    if kind in ("restock", "damage") and qty <= 0:
        raise ValidationError("Enter a quantity greater than 0", code="VALIDATION_ERROR")
    if kind == "correction" and qty == 0:
        raise ValidationError("A correction must change the quantity", code="VALIDATION_ERROR")
    if kind in ("damage", "correction") and not (note and note.strip()):
        raise ValidationError(
            "Add a note explaining the damage or correction", code="NOTE_REQUIRED"
        )
    change = qty if kind in ("restock", "correction") else -qty

    with transaction():
        product: Product | None = db.session.scalar(
            select(Product).where(Product.id == product_id).with_for_update(of=Product)
        )
        if product is None:
            raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
        before = product.quantity
        apply_movement(product, change, ADJUST_REASONS[kind], actor, note=note)
        audit_service.record(
            actor,
            "stock.adjust",
            "product",
            product.id,
            f"{product.code} {product.name}: {kind} {change:+d} ({before} → {product.quantity})",
            changes={"quantity": [before, product.quantity]},
            metadata={"change": change, "reason": kind, "note": note},
        )
    return product


def movements(product_id: int, page: int, page_size: int) -> tuple[list[StockMovement], int]:
    from sqlalchemy import func, select

    stmt = select(StockMovement).where(StockMovement.product_id == product_id)
    total = int(db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.session.scalars(
        stmt.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(rows), total


def verify() -> list[dict[str, object]]:
    """OS-4: products.quantity must equal the sum of its ledger. Returns mismatches (ideally [])."""
    from sqlalchemy import func, select

    ledger = (
        select(StockMovement.product_id, func.sum(StockMovement.change).label("total"))
        .group_by(StockMovement.product_id)
        .subquery()
    )
    rows = db.session.execute(
        select(Product.id, Product.code, Product.quantity, func.coalesce(ledger.c.total, 0))
        .outerjoin(ledger, ledger.c.product_id == Product.id)
        .where(Product.quantity != func.coalesce(ledger.c.total, 0))
        .order_by(Product.id)
    ).all()
    return [{"id": r[0], "code": r[1], "quantity": r[2], "ledger_total": int(r[3])} for r in rows]
