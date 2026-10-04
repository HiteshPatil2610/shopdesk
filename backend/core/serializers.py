"""JSON shapes for products. Two separate functions so the POS one can't leak cost (BR-12)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from core.media import image_url
from core.models import Category, Product, StockMovement
from core.money import money_str
from core.pricing import margin_pct


def category_out(category: Category) -> dict[str, Any]:
    return {"id": category.id, "name": category.name, "is_active": category.is_active}


def product_out(p: Product) -> dict[str, Any]:
    """Admin view: everything, including cost and margins."""
    cost = Decimal(p.cost_price)
    mp_margin = margin_pct(Decimal(p.market_price), cost)
    sp_margin = margin_pct(Decimal(p.selling_price), cost)
    return {
        "id": p.id,
        "code": p.code,
        "barcode": p.barcode,
        "name": p.name,
        "description": p.description,
        "category": category_out(p.category) if p.category else None,
        "unit": p.unit,
        "image_url": image_url(p.image_public_id, "full"),
        "thumb_url": image_url(p.image_public_id, "thumb"),
        "cost_price": money_str(p.cost_price),
        "market_price": money_str(p.market_price),
        "selling_price": money_str(p.selling_price),
        "mp_is_manual": p.mp_is_manual,
        "sp_is_manual": p.sp_is_manual,
        "mp_round_mode": p.mp_round_mode,
        "mp_margin_pct": money_str(mp_margin) if mp_margin is not None else None,
        "sp_margin_pct": money_str(sp_margin) if sp_margin is not None else None,
        "quantity": p.quantity,
        "reorder_level": p.reorder_level,
        "low_stock": p.low_stock,
        "is_active": p.is_active,
        "version": p.version,
        "updated_by": p.updater.display_name if p.updater else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


POS_FIELDS = frozenset(
    {
        "id",
        "code",
        "barcode",
        "name",
        "unit",
        "image_url",
        "thumb_url",
        "market_price",
        "selling_price",
        "quantity",
        "low_stock",
    }
)


def pos_product_out(p: Product) -> dict[str, Any]:
    """Billing Counter view: built from scratch — no cost, no margins (BR-12)."""
    return {
        "id": p.id,
        "code": p.code,
        "barcode": p.barcode,
        "name": p.name,
        "unit": p.unit,
        "image_url": image_url(p.image_public_id, "full"),
        "thumb_url": image_url(p.image_public_id, "thumb"),
        "market_price": money_str(p.market_price),
        "selling_price": money_str(p.selling_price),
        "quantity": p.quantity,
        "low_stock": p.low_stock,
    }


def movement_out(m: StockMovement) -> dict[str, Any]:
    return {
        "id": m.id,
        "change": m.change,
        "quantity_after": m.quantity_after,
        "reason": m.reason,
        "reference_type": m.reference_type,
        "reference_id": m.reference_id,
        "note": m.note,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def page_out(items: list[dict[str, Any]], page: int, page_size: int, total: int) -> dict[str, Any]:
    return {"items": items, "page": page, "page_size": page_size, "total": total}
