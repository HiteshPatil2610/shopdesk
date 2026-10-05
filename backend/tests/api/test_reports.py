"""Spec 08: dashboard & reports — sums, IST day boundaries, snapshots, roles, CSV."""

import csv
import io
import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from core.models import AuditLog, Order, OrderItem, Product

pytestmark = pytest.mark.db

IST = ZoneInfo("Asia/Kolkata")
DAY = "2026-10-01"


def ist(ts: str) -> datetime:
    return datetime.fromisoformat(ts).replace(tzinfo=IST)


@pytest.fixture()
def product(dbs, staff):
    p = Product(
        code="P90001",
        name="Steel bottle",
        cost_price=200,
        market_price=300,
        selling_price=260,
        quantity=50,
    )
    dbs.add(p)
    dbs.flush()
    return p


def add_order(
    dbs,
    staff,
    product,
    *,
    at,
    total,
    cost,
    status="confirmed",
    qty=1,
    discount="0",
    name="Amit",
    cashier="cashier",
):
    order = Order(
        order_number=f"T-{uuid.uuid4().hex[:10]}",
        status=status,
        customer_name=name,
        cashier_id=staff[cashier].id,
        discount_applied=Decimal(discount) > 0,
        payment_mode="cash" if status == "confirmed" else None,
        item_count=qty,
        subtotal_mp=Decimal(total) + Decimal(discount),
        discount_amount=Decimal(discount),
        total_amount=Decimal(total),
        total_cost=Decimal(cost),
        idempotency_key=uuid.uuid4(),
        created_at=at,
    )
    order.items.append(
        OrderItem(
            product_id=product.id,
            product_code=product.code,
            product_name=product.name,
            quantity=qty,
            unit_cost=Decimal(cost) / qty,
            unit_mp=product.market_price,
            unit_sp=product.selling_price,
            unit_price_charged=Decimal(total) / qty,
            line_total=Decimal(total),
        )
    )
    dbs.add(order)
    dbs.flush()
    return order


@pytest.fixture()
def seeded(dbs, staff, product):
    add_order(dbs, staff, product, at=ist(f"{DAY} 10:00"), total="605", cost="400", discount="80")
    add_order(dbs, staff, product, at=ist(f"{DAY} 12:30"), total="300", cost="200", name="Neha")
    add_order(dbs, staff, product, at=ist(f"{DAY} 23:59"), total="85", cost="60", cashier="manager")
    add_order(dbs, staff, product, at=ist(f"{DAY} 15:00"), total="999", cost="1", status="rejected")
    add_order(
        dbs, staff, product, at=ist("2026-10-02 00:01"), total="50", cost="40"
    )  # next IST day
    add_order(
        dbs, staff, product, at=ist("2026-09-30 18:00"), total="200", cost="150"
    )  # previous day
    return product


def test_summary_counts_only_confirmed_and_uses_ist_days(dbs, client, as_role, seeded):
    s = client.get(f"/api/admin/reports/summary?date={DAY}", headers=as_role("manager")).get_json()
    assert s["sales_total"] == "990.00"  # 605 + 300 + 85; the 00:01 order belongs to 2 Oct
    assert s["profit_total"] == "330.00"  # 205 + 100 + 25
    assert s["discount_total"] == "80.00"
    assert (s["orders_confirmed"], s["orders_rejected"], s["items_sold"]) == (3, 1, 3)
    assert s["avg_order_value"] == "330.00"
    assert s["previous"]["date"] == "2026-09-30" and s["previous"]["sales_total"] == "200.00"
    assert s["change_pct"]["sales_total"] == "395.00"  # 990 vs 200
    assert s["change_pct"]["orders_confirmed"] == "200.00"  # 3 vs 1
    next_day = client.get(
        "/api/admin/reports/summary?date=2026-10-02", headers=as_role("manager")
    ).get_json()
    assert next_day["sales_total"] == "50.00"


def test_profit_uses_snapshots_not_current_cost(dbs, client, as_role, seeded):
    seeded.cost_price = Decimal("250")  # cost changes later; history must not
    dbs.flush()
    s = client.get(f"/api/admin/reports/summary?date={DAY}", headers=as_role("manager")).get_json()
    assert s["profit_total"] == "330.00"


def test_sales_by_day_is_zero_filled(dbs, client, as_role, seeded):
    items = client.get(
        "/api/admin/reports/sales-by-day?from=2026-09-29&to=2026-10-03", headers=as_role("manager")
    ).get_json()["items"]
    assert [(i["date"], i["sales_total"], i["orders"]) for i in items] == [
        ("2026-09-29", "0.00", 0),
        ("2026-09-30", "200.00", 1),
        ("2026-10-01", "990.00", 3),
        ("2026-10-02", "50.00", 1),
        ("2026-10-03", "0.00", 0),
    ]


def test_top_products_and_cashiers(dbs, client, as_role, seeded):
    h = as_role("manager")
    top = client.get(f"/api/admin/reports/top-products?from={DAY}&to={DAY}", headers=h).get_json()[
        "items"
    ]
    assert top == [
        {
            "product_id": seeded.id,
            "code": "P90001",
            "name": "Steel bottle",
            "qty": 3,
            "revenue": "990.00",
            "profit": "330.00",
        }
    ]
    people = client.get(f"/api/admin/reports/cashiers?from={DAY}&to={DAY}", headers=h).get_json()[
        "items"
    ]
    assert [
        (p["cashier"], p["orders"], p["sales_total"], p["rejected"], p["discounts_given"])
        for p in people
    ] == [
        ("cashier", 2, "905.00", 1, "80.00"),
        ("manager", 1, "85.00", 0, "0.00"),
    ]


def test_low_stock_list(dbs, client, as_role, staff):
    dbs.add_all(
        [
            Product(
                code="P90010",
                name="Low",
                cost_price=1,
                market_price=2,
                selling_price=2,
                quantity=2,
                reorder_level=5,
            ),
            Product(
                code="P90011",
                name="Out",
                cost_price=1,
                market_price=2,
                selling_price=2,
                quantity=0,
                reorder_level=5,
            ),
            Product(
                code="P90012",
                name="Fine",
                cost_price=1,
                market_price=2,
                selling_price=2,
                quantity=50,
                reorder_level=5,
            ),
            Product(
                code="P90013",
                name="Gone",
                cost_price=1,
                market_price=2,
                selling_price=2,
                quantity=0,
                is_active=False,
            ),
        ]
    )
    dbs.flush()
    h = as_role("manager")
    items = client.get("/api/admin/reports/low-stock", headers=h).get_json()["items"]
    assert [i["code"] for i in items] == ["P90011", "P90010"]
    s = client.get("/api/admin/reports/summary", headers=h).get_json()
    assert (s["low_stock_count"], s["out_of_stock_count"]) == (2, 1)


def test_bad_ranges_are_rejected(dbs, client, as_role):
    h = as_role("manager")
    assert (
        client.get(
            "/api/admin/reports/sales-by-day?from=2026-10-05&to=2026-10-01", headers=h
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/api/admin/reports/sales-by-day?from=2024-01-01&to=2026-01-01", headers=h
        ).status_code
        == 400
    )


def test_cashier_has_no_access_and_pos_has_no_reports(dbs, client, as_role):
    assert client.get("/api/admin/reports/summary", headers=as_role("cashier")).status_code == 403
    assert (
        client.get("/api/pos/reports/summary", headers=as_role("cashier", pos=True)).status_code
        == 404
    )


def test_sales_csv_is_admin_only_audited_and_formula_safe(dbs, client, as_role, staff, product):
    add_order(
        dbs,
        staff,
        product,
        at=ist(f"{DAY} 11:00"),
        total="300",
        cost="200",
        name="=HYPERLINK(evil)",
    )
    assert (
        client.get(
            f"/api/admin/reports/sales.csv?from={DAY}&to={DAY}", headers=as_role("manager")
        ).status_code
        == 403
    )
    res = client.get(f"/api/admin/reports/sales.csv?from={DAY}&to={DAY}", headers=as_role("admin"))
    assert res.status_code == 200 and "attachment" in res.headers["Content-Disposition"]
    rows = list(csv.reader(io.StringIO(res.get_data(as_text=True).lstrip("﻿"))))
    assert rows[0][:5] == ["date", "invoice", "customer", "cashier", "code"]
    assert rows[1][2] == "'=HYPERLINK(evil)" and rows[1][10] == "100.00"
    audit = dbs.scalar(select(AuditLog).where(AuditLog.action == "report.export"))
    assert audit.metadata_["row_count"] == 1 and audit.actor_username == "admin"
