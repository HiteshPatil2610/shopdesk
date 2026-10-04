"""Server-authoritative billing quotes (PB-1 through PB-4, BR-12)."""

from decimal import Decimal
from typing import cast

from sqlalchemy import select
from sqlalchemy.engine import ScalarResult

from core.db import db
from core.errors import ValidationError
from core.media import image_url
from core.models import Product
from core.money import money_str
from core.schemas.orders import QuoteItem, QuoteLine, QuoteResponse


def quote(items: list[QuoteItem], discount_applied: bool) -> QuoteResponse:
    """Merge codes and quote stored prices without writes; reject merged qty over 10,000."""
    quantities: dict[str, int] = {}
    for item in items:
        quantities[item.code] = quantities.get(item.code, 0) + item.qty
    if any(qty > 10_000 for qty in quantities.values()):
        raise ValidationError("Combined quantity must not exceed 10,000 per product")
    rows = cast(
        ScalarResult[Product],
        db.session.scalars(select(Product).where(Product.code.in_(quantities))),
    )
    products = {product.code: product for product in rows}
    lines = [
        _quote_line(code, qty, products.get(code), discount_applied)
        for code, qty in quantities.items()
    ]
    subtotal = sum((Decimal(line.unit_mp) * line.qty for line in lines), Decimal(0))
    total = sum((Decimal(line.line_total) for line in lines), Decimal(0))
    return QuoteResponse(
        discount_applied=discount_applied,
        lines=lines,
        item_count=sum(quantities.values()),
        subtotal_mp=money_str(subtotal),
        discount_amount=money_str(subtotal - total),
        total=money_str(total),
        can_confirm=bool(lines) and all(line.status == "ok" for line in lines),
    )


def _quote_line(code: str, qty: int, product: Product | None, discount: bool) -> QuoteLine:
    if product is None:
        return QuoteLine(
            code=code,
            qty=qty,
            available=0,
            unit_mp="0.00",
            unit_sp="0.00",
            unit_price="0.00",
            line_total="0.00",
            status="not_found",
        )
    price = product.selling_price if discount else product.market_price
    return QuoteLine(
        code=code,
        name=product.name,
        thumb_url=image_url(product.image_public_id, "thumb"),
        qty=qty,
        available=product.quantity,
        unit_mp=money_str(product.market_price),
        unit_sp=money_str(product.selling_price),
        unit_price=money_str(price),
        line_total=money_str(price * qty),
        status=(
            "inactive"
            if not product.is_active
            else "insufficient_stock" if qty > product.quantity else "ok"
        ),
    )
