"""Dashboard & reports (spec 08). Read-only aggregates computed in SQL with NUMERIC (BR-1).

Only CONFIRMED orders count towards sales and profit; rejected orders are a separate count.
Days are shop-local (IST) calendar days. Profit comes from the price snapshots in order_items.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, case, cast, func, select

from core.actor import ActorContext
from core.db import db, transaction
from core.models import Order, OrderItem, Product, User
from core.money import money_str
from core.services import audit_service
from core.services.audit_view_service import csv_cell
from core.timeutil import day_bounds_utc, shop_tz

ZERO = Decimal("0")


def _local_date(column: Any) -> Any:
    """created_at (UTC) → the shop-local calendar date, in SQL."""
    return cast(func.timezone(str(shop_tz()), column), Date)


def _range_bounds(start: date, end: date) -> tuple[Any, Any]:
    return day_bounds_utc(start)[0], day_bounds_utc(end)[1]


def _money(value: Any) -> str:
    return money_str(Decimal(value or 0))


def _day_totals(day: date) -> dict[str, Any]:
    start, end = day_bounds_utc(day)
    confirmed = Order.status == "confirmed"
    row = db.session.execute(
        select(
            func.coalesce(func.sum(case((confirmed, Order.total_amount))), 0),
            func.coalesce(func.sum(case((confirmed, Order.total_amount - Order.total_cost))), 0),
            func.coalesce(func.sum(case((confirmed, Order.discount_amount))), 0),
            func.count(case((confirmed, Order.id))),
            func.count(case((Order.status == "rejected", Order.id))),
            func.coalesce(func.sum(case((confirmed, Order.item_count))), 0),
        ).where(Order.created_at >= start, Order.created_at < end)
    ).one()
    sales, profit, discount, n_confirmed, n_rejected, items = row
    avg = Decimal(sales) / n_confirmed if n_confirmed else ZERO
    return {
        "sales_total": _money(sales),
        "profit_total": _money(profit),
        "discount_total": _money(discount),
        "orders_confirmed": int(n_confirmed),
        "orders_rejected": int(n_rejected),
        "items_sold": int(items),
        "avg_order_value": _money(avg),
    }


def _change_pct(today: Decimal, before: Decimal) -> str | None:
    """Percent change vs the previous day (None when there's nothing to compare with)."""
    if before == 0:
        return None
    return money_str((today - before) / before * 100)


def summary(day: date) -> dict[str, Any]:
    low = db.session.execute(
        select(
            func.count(case((Product.quantity <= Product.reorder_level, Product.id))),
            func.count(case((Product.quantity == 0, Product.id))),
        ).where(Product.is_active)
    ).one()
    today = _day_totals(day)
    previous = _day_totals(day - timedelta(days=1))
    return {
        "date": day.isoformat(),
        **today,
        "low_stock_count": int(low[0]),
        "out_of_stock_count": int(low[1]),
        "previous": {"date": (day - timedelta(days=1)).isoformat(), **previous},
        "change_pct": {
            key: _change_pct(Decimal(str(today[key])), Decimal(str(previous[key])))
            for key in ("sales_total", "profit_total", "orders_confirmed")
        },
    }


def sales_by_day(start: date, end: date) -> list[dict[str, Any]]:
    """One row per day in [start, end], zero-filled."""
    lo, hi = _range_bounds(start, end)
    local_day = _local_date(Order.created_at)
    rows = db.session.execute(
        select(
            local_day,
            func.sum(Order.total_amount),
            func.sum(Order.total_amount - Order.total_cost),
            func.count(Order.id),
        )
        .where(Order.status == "confirmed", Order.created_at >= lo, Order.created_at < hi)
        .group_by(local_day)
    ).all()
    by_day = {r[0]: r for r in rows}
    out = []
    day = start
    while day <= end:
        r = by_day.get(day)
        out.append(
            {
                "date": day.isoformat(),
                "sales_total": _money(r[1] if r else 0),
                "profit_total": _money(r[2] if r else 0),
                "orders": int(r[3]) if r else 0,
            }
        )
        day += timedelta(days=1)
    return out


def top_products(start: date, end: date, limit: int, by: str) -> list[dict[str, Any]]:
    lo, hi = _range_bounds(start, end)
    qty = func.sum(OrderItem.quantity)
    revenue = func.sum(OrderItem.line_total)
    profit = func.sum((OrderItem.unit_price_charged - OrderItem.unit_cost) * OrderItem.quantity)
    rows = db.session.execute(
        select(
            OrderItem.product_id,
            func.max(OrderItem.product_code),
            func.max(OrderItem.product_name),
            qty,
            revenue,
            profit,
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status == "confirmed", Order.created_at >= lo, Order.created_at < hi)
        .group_by(OrderItem.product_id)
        .order_by((qty if by == "qty" else revenue).desc(), OrderItem.product_id)
        .limit(limit)
    ).all()
    return [
        {
            "product_id": r[0],
            "code": r[1],
            "name": r[2],
            "qty": int(r[3]),
            "revenue": _money(r[4]),
            "profit": _money(r[5]),
        }
        for r in rows
    ]


def low_stock(limit: int = 50) -> list[dict[str, Any]]:
    rows = db.session.scalars(
        select(Product)
        .where(Product.is_active, Product.quantity <= Product.reorder_level)
        .order_by(Product.quantity, Product.reorder_level.desc(), Product.name)
        .limit(limit)
    ).all()
    return [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "quantity": p.quantity,
            "reorder_level": p.reorder_level,
            "unit": p.unit,
            "version": p.version,
        }
        for p in rows
    ]


def cashiers(start: date, end: date) -> list[dict[str, Any]]:
    lo, hi = _range_bounds(start, end)
    confirmed = Order.status == "confirmed"
    rows = db.session.execute(
        select(
            Order.cashier_id,
            func.max(func.coalesce(User.username, User.full_name)),
            func.count(case((confirmed, Order.id))),
            func.coalesce(func.sum(case((confirmed, Order.total_amount))), 0),
            func.count(case((Order.status == "rejected", Order.id))),
            func.count(case((confirmed & Order.discount_applied, Order.id))),
            func.coalesce(func.sum(case((confirmed, Order.discount_amount))), 0),
        )
        .join(User, User.id == Order.cashier_id)
        .where(Order.created_at >= lo, Order.created_at < hi)
        .group_by(Order.cashier_id)
        .order_by(func.coalesce(func.sum(case((confirmed, Order.total_amount))), 0).desc())
    ).all()
    return [
        {
            "cashier_id": r[0],
            "cashier": r[1],
            "orders": int(r[2]),
            "sales_total": _money(r[3]),
            "rejected": int(r[4]),
            "discount_orders": int(r[5]),
            "discounts_given": _money(r[6]),
        }
        for r in rows
    ]


CSV_COLUMNS = [
    "date",
    "invoice",
    "customer",
    "cashier",
    "code",
    "product",
    "qty",
    "unit_price",
    "line_total",
    "unit_cost",
    "profit",
    "discount_applied",
    "payment_mode",
]


def sales_csv(start: date, end: date, actor: ActorContext) -> Iterator[str]:
    """One row per confirmed order line. The export itself is audited (report.export)."""
    lo, hi = _range_bounds(start, end)
    stmt = (
        select(Order, OrderItem)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(Order.status == "confirmed", Order.created_at >= lo, Order.created_at < hi)
        .order_by(Order.created_at, Order.id, OrderItem.id)
    )
    count = int(db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    with transaction():
        audit_service.record(
            actor,
            "report.export",
            "report",
            None,
            f"Exported sales {start.isoformat()} → {end.isoformat()} ({count} lines)",
            metadata={
                "report": "sales",
                "from": start.isoformat(),
                "to": end.isoformat(),
                "row_count": count,
            },
        )

    tz = shop_tz()

    def generate() -> Iterator[str]:
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(CSV_COLUMNS)
        yield "﻿" + buffer.getvalue()  # BOM so Excel opens ₹/Hindi names correctly
        for order, item in db.session.execute(stmt.execution_options(yield_per=500)):
            buffer.seek(0)
            buffer.truncate(0)
            profit = (Decimal(item.unit_price_charged) - Decimal(item.unit_cost)) * item.quantity
            writer.writerow(
                [
                    csv_cell(order.created_at.astimezone(tz).strftime("%Y-%m-%d %H:%M")),
                    csv_cell(order.order_number),
                    csv_cell(order.customer_name),
                    csv_cell(order.cashier.display_name if order.cashier else ""),
                    csv_cell(item.product_code),
                    csv_cell(item.product_name),
                    item.quantity,
                    money_str(item.unit_price_charged),
                    money_str(item.line_total),
                    money_str(item.unit_cost),
                    money_str(profit),
                    "yes" if order.discount_applied else "no",
                    order.payment_mode or "",
                ]
            )
            yield buffer.getvalue()

    return generate()
