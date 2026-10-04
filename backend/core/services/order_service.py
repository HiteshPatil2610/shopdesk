"""Billing: server-authoritative quotes (spec 06) and the confirm/reject transactions (spec 07).

Prices always come from the database rows, never from the browser (BR-5).
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import func, or_, select, text
from sqlalchemy.engine import ScalarResult
from sqlalchemy.exc import IntegrityError

from core.actor import ActorContext
from core.db import db, transaction
from core.errors import (
    BusinessRuleError,
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)
from core.media import image_url
from core.models import Order, OrderItem, Product
from core.models.base import utcnow
from core.money import money_str
from core.schemas.orders import (
    ConfirmRequest,
    QuoteItem,
    QuoteLine,
    QuoteResponse,
    RejectRequest,
)
from core.services import audit_service, stock_service
from core.timeutil import day_bounds_utc, shop_today

MAX_QTY = 10_000
RECEIPT_WINDOW = timedelta(hours=24)


def _merge(items: list[QuoteItem]) -> dict[str, int]:
    """PB-2: duplicate codes become one line with the summed quantity."""
    quantities: dict[str, int] = {}
    for item in items:
        quantities[item.code] = quantities.get(item.code, 0) + item.qty
    if any(qty > MAX_QTY for qty in quantities.values()):
        raise ValidationError("Combined quantity must not exceed 10,000 per product")
    return quantities


# --- quote (spec 06) --------------------------------------------------------------------


def quote(items: list[QuoteItem], discount_applied: bool) -> QuoteResponse:
    """Merge codes and quote stored prices without writes."""
    quantities = _merge(items)
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


# --- numbering & helpers (spec 07) ------------------------------------------------------


def by_idempotency_key(key: uuid.UUID) -> Order | None:
    order: Order | None = db.session.scalar(select(Order).where(Order.idempotency_key == key))
    return order


def next_number(kind: str) -> str:
    """INV-/REJ-YYYYMMDD-NNNN; NNNN restarts every shop-local day (OS-1/OS-2).

    One atomic upsert: concurrent confirms queue on the counter row inside their transactions,
    so numbers are unique. A rolled-back sale may leave a gap, which is allowed.
    """
    day = shop_today()
    value = db.session.scalar(
        text(
            "INSERT INTO daily_counters (counter_date, kind, last_value) VALUES (:d, :k, 1) "
            "ON CONFLICT (counter_date, kind) "
            "DO UPDATE SET last_value = daily_counters.last_value + 1 RETURNING last_value"
        ),
        {"d": day, "k": kind},
    )
    return f"{kind}-{day:%Y%m%d}-{int(value):04d}"


def _summary(order: Order, lines: int) -> str:
    prefix = "" if order.status == "confirmed" else "REJECTED · "
    extra = " (discount)" if order.discount_applied else ""
    return (
        f"{prefix}{order.order_number} · {order.customer_name} · {order.item_count} item(s) "
        f"in {lines} line(s) · ₹{money_str(order.total_amount)}{extra}"
    )[:255]


def _audit_metadata(order: Order, actor: ActorContext, **extra: Any) -> dict[str, Any]:
    return {
        "order_number": order.order_number,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "cashier": actor.username,
        "discount_applied": order.discount_applied,
        "payment_mode": order.payment_mode,
        "item_count": order.item_count,
        "total": money_str(order.total_amount),
        "lines": [
            {
                "code": item.product_code,
                "qty": item.quantity,
                "unit_price": money_str(item.unit_price_charged),
            }
            for item in order.items
        ],
        **extra,
    }


def _build_items(
    order: Order, products: list[Product], quantities: dict[str, int], discount: bool
) -> None:
    """Copy prices into the order lines (BR-6) and compute totals with Decimal."""
    subtotal = total = cost = Decimal(0)
    count = 0
    for product in products:
        qty = quantities[product.code]
        unit_price = Decimal(product.selling_price if discount else product.market_price)
        line_total = unit_price * qty
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_code=product.code,
                product_name=product.name,
                quantity=qty,
                unit_cost=product.cost_price,
                unit_mp=product.market_price,
                unit_sp=product.selling_price,
                unit_price_charged=unit_price,
                line_total=line_total,
            )
        )
        subtotal += Decimal(product.market_price) * qty
        total += line_total
        cost += Decimal(product.cost_price) * qty
        count += qty
    order.item_count = count
    order.subtotal_mp = subtotal
    order.total_amount = total
    order.discount_amount = subtotal - total
    order.total_cost = cost


# --- confirm / reject -------------------------------------------------------------------


def confirm(req: ConfirmRequest, actor: ActorContext) -> tuple[Order, bool]:
    """The sale transaction (architecture §6.4). Returns (order, created).

    Rows are locked in id order (no deadlocks) and stock is re-checked under the lock; prices
    come from the locked rows; order, items, stock, ledger and audit commit together or not at
    all (BR-7). The DB CHECK (quantity >= 0) is the last line of defence.
    """
    existing = by_idempotency_key(req.idempotency_key)
    if existing:
        return existing, False  # BR-11: a double click or retry never makes a second order
    quantities = _merge(req.items)
    try:
        with transaction():
            products = list(
                db.session.scalars(
                    select(Product)
                    .where(Product.code.in_(quantities))
                    .order_by(Product.id)
                    .with_for_update(of=Product)
                ).all()
            )
            by_code = {p.code: p for p in products}
            unavailable = [c for c in quantities if c not in by_code or not by_code[c].is_active]
            if unavailable:
                raise BusinessRuleError(
                    f"Not available for sale: {', '.join(unavailable)}",
                    code="PRODUCT_UNAVAILABLE",
                    details=[{"code": c} for c in unavailable],
                )
            short = [
                {"code": p.code, "requested": quantities[p.code], "available": p.quantity}
                for p in products
                if quantities[p.code] > p.quantity
            ]
            if short:
                raise InsufficientStockError(
                    f"Not enough stock for {len(short)} item(s)", details=short
                )

            order = Order(
                order_number=next_number("INV"),
                status="confirmed",
                customer_name=req.customer_name,
                customer_phone=req.customer_phone,
                cashier_id=actor.user_id,
                discount_applied=req.discount_applied,
                payment_mode=req.payment_mode,
                idempotency_key=req.idempotency_key,
            )
            _build_items(order, products, quantities, req.discount_applied)
            db.session.add(order)
            db.session.flush()
            for product in products:
                stock_service.apply_movement(
                    product,
                    -quantities[product.code],
                    "sale",
                    actor,
                    reference_type="order",
                    reference_id=order.id,
                )
            audit_service.record(
                actor,
                "order.confirm",
                "order",
                order.id,
                _summary(order, len(products)),
                metadata=_audit_metadata(order, actor),
            )
    except IntegrityError:
        db.session.rollback()
        raced = by_idempotency_key(req.idempotency_key)  # same key confirmed concurrently
        if raced:
            return raced, False
        raise
    return order, True


def reject(req: RejectRequest, actor: ActorContext) -> tuple[Order, bool]:
    """Save the abandoned cart for traceability: prices snapshotted, no lock, NO stock change."""
    existing = by_idempotency_key(req.idempotency_key)
    if existing:
        return existing, False
    quantities = _merge(req.items)
    products: list[Product] = []
    if quantities:
        products = list(
            db.session.scalars(
                select(Product).where(Product.code.in_(quantities)).order_by(Product.id)
            ).all()
        )
    known = {p.code for p in products}
    skipped = [code for code in quantities if code not in known]
    try:
        with transaction():
            order = Order(
                order_number=next_number("REJ"),
                status="rejected",
                customer_name=(req.customer_name or "").strip() or "Walk-in customer",
                cashier_id=actor.user_id,
                discount_applied=req.discount_applied,
                payment_mode=None,
                reject_reason=req.reason or None,
                idempotency_key=req.idempotency_key,
            )
            _build_items(order, products, quantities, req.discount_applied)
            db.session.add(order)
            db.session.flush()
            audit_service.record(
                actor,
                "order.reject",
                "order",
                order.id,
                _summary(order, len(products)),
                metadata=_audit_metadata(
                    order, actor, reject_reason=req.reason, skipped_codes=skipped
                ),
            )
    except IntegrityError:
        db.session.rollback()
        raced = by_idempotency_key(req.idempotency_key)
        if raced:
            return raced, False
        raise
    return order, True


# --- reading ------------------------------------------------------------------------------


def get(order_id: int) -> Order:
    order: Order | None = db.session.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")
    return order


def get_by_number(order_number: str) -> Order:
    order: Order | None = db.session.scalar(
        select(Order).where(Order.order_number == order_number.strip().upper())
    )
    if order is None:
        raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")
    return order


def receipt_order(order_number: str, actor: ActorContext) -> Order:
    """Cashiers may reprint only their own orders from the last 24h; managers and admins any."""
    order = get_by_number(order_number)
    if actor.role == "cashier" and (
        order.cashier_id != actor.user_id or utcnow() - order.created_at > RECEIPT_WINDOW
    ):
        raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")
    return order


def my_orders_today(actor: ActorContext) -> list[Order]:
    start, end = day_bounds_utc(shop_today())
    return list(
        db.session.scalars(
            select(Order)
            .where(
                Order.cashier_id == actor.user_id,
                Order.created_at >= start,
                Order.created_at < end,
            )
            .order_by(Order.created_at.desc())
        ).all()
    )


def list_orders(query: Any) -> tuple[list[Order], int]:
    """Admin order list with filters (spec 07 §6)."""
    stmt = select(Order)
    if query.status:
        stmt = stmt.where(Order.status == query.status)
    if query.cashier_id:
        stmt = stmt.where(Order.cashier_id == query.cashier_id)
    if query.from_at:
        stmt = stmt.where(Order.created_at >= query.from_at)
    if query.to_at:
        stmt = stmt.where(Order.created_at <= query.to_at)
    if query.q:
        term = f"%{query.q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Order.customer_name).like(term),
                func.lower(Order.order_number).like(term),
            )
        )
    total = int(db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.session.scalars(
        stmt.order_by(Order.created_at.desc(), Order.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    return list(rows), total
