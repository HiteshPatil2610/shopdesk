"""Spec 07: confirm/reject, stock ledger, receipts, admin orders and stock adjustments."""

import json
import uuid
from datetime import timedelta

import pytest
from freezegun import freeze_time
from sqlalchemy import func, select

from core.models import AuditLog, Order, Product, StockMovement
from core.serializers import POS_FIELDS

pytestmark = pytest.mark.db


@pytest.fixture()
def catalogue(dbs, admin_client, as_role):
    """Steel bottle: MP 420 / SP 370 (cost 212), qty 4.  Notebook: cost 40, qty 9."""
    h = as_role("manager")
    bottle = admin_client.post(
        "/api/products",
        headers=h,
        json={"name": "Steel bottle", "cost_price": "212", "quantity": "4"},
    ).get_json()["product"]
    notebook = admin_client.post(
        "/api/products",
        headers=h,
        json={"name": "Notebook A5", "cost_price": "40", "quantity": "9"},
    ).get_json()["product"]
    return {"bottle": bottle, "notebook": notebook}


def body(items, **overrides):
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "customer_name": "Amit Kumar",
        "customer_phone": "9876543210",
        "payment_mode": "upi",
        "discount_applied": False,
        "items": items,
    }
    payload.update(overrides)
    return payload


def qty_of(dbs, product_id):
    dbs.expire_all()
    return dbs.get(Product, product_id).quantity


def test_confirm_reduces_stock_writes_ledger_snapshot_and_audit(
    dbs, pos_client, as_role, catalogue
):
    b = catalogue["bottle"]
    res = pos_client.post(
        "/api/orders/confirm",
        headers=as_role("cashier", pos=True),
        json=body([{"code": b["code"], "qty": 2}]),
    )
    assert res.status_code == 201, res.get_json()
    order = res.get_json()["order"]
    assert order["status"] == "confirmed" and order["order_number"].startswith("INV-")
    assert (order["total"], order["subtotal_mp"], order["discount_amount"]) == (
        "840.00",
        "840.00",
        "0.00",
    )
    assert order["cashier_name"] == "cashier" and order["customer_name"] == "Amit Kumar"
    assert qty_of(dbs, b["id"]) == 2  # 4 − 2 = 2
    [move] = dbs.scalars(select(StockMovement).where(StockMovement.reason == "sale")).all()
    assert (move.change, move.quantity_after, move.reference_type) == (-2, 2, "order")
    [audit] = dbs.scalars(select(AuditLog).where(AuditLog.action == "order.confirm")).all()
    assert audit.source == "pos" and audit.metadata_["customer_name"] == "Amit Kumar"
    assert audit.metadata_["total"] == "840.00"


def test_discount_uses_selling_price(dbs, pos_client, as_role, catalogue):
    b, n = catalogue["bottle"], catalogue["notebook"]
    res = pos_client.post(
        "/api/orders/confirm",
        headers=as_role("cashier", pos=True),
        json=body(
            [{"code": b["code"], "qty": 1}, {"code": n["code"], "qty": 2}], discount_applied=True
        ),
    )
    order = res.get_json()["order"]
    # MP 420 + 2×80 = 580; SP 370 + 2×70 = 510
    assert (order["subtotal_mp"], order["total"], order["discount_amount"]) == (
        "580.00",
        "510.00",
        "70.00",
    )


def test_insufficient_stock_rolls_back_everything(dbs, pos_client, as_role, catalogue):
    b, n = catalogue["bottle"], catalogue["notebook"]
    res = pos_client.post(
        "/api/orders/confirm",
        headers=as_role("cashier", pos=True),
        json=body([{"code": n["code"], "qty": 1}, {"code": b["code"], "qty": 5}]),
    )
    assert res.status_code == 409
    err = res.get_json()["error"]
    assert err["code"] == "INSUFFICIENT_STOCK"
    assert err["details"] == [{"code": b["code"], "requested": 5, "available": 4}]
    assert qty_of(dbs, n["id"]) == 9 and qty_of(dbs, b["id"]) == 4
    assert dbs.scalar(select(func.count()).select_from(Order)) == 0


def test_unknown_or_inactive_product_is_422(dbs, admin_client, pos_client, as_role, catalogue):
    b = catalogue["bottle"]
    admin_client.post(f"/api/products/{b['id']}/deactivate", headers=as_role("manager"))
    res = pos_client.post(
        "/api/orders/confirm",
        headers=as_role("cashier", pos=True),
        json=body([{"code": b["code"], "qty": 1}, {"code": "P99999", "qty": 1}]),
    )
    assert res.status_code == 422 and res.get_json()["error"]["code"] == "PRODUCT_UNAVAILABLE"


def test_same_idempotency_key_creates_one_order(dbs, pos_client, as_role, catalogue):
    payload = body([{"code": catalogue["bottle"]["code"], "qty": 1}])
    h = as_role("cashier", pos=True)
    first = pos_client.post("/api/orders/confirm", headers=h, json=payload)
    second = pos_client.post("/api/orders/confirm", headers=h, json=payload)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.get_json()["order"]["order_number"] == second.get_json()["order"]["order_number"]
    assert qty_of(dbs, catalogue["bottle"]["id"]) == 3
    assert dbs.scalar(select(func.count()).select_from(Order)) == 1


def test_browser_prices_are_ignored(dbs, pos_client, as_role, catalogue):
    items = [{"code": catalogue["bottle"]["code"], "qty": 1, "unit_price": "1.00"}]
    res = pos_client.post(
        "/api/orders/confirm", headers=as_role("cashier", pos=True), json=body(items, total="1.00")
    )
    assert res.get_json()["order"]["total"] == "420.00"


def test_old_orders_keep_their_prices(dbs, admin_client, pos_client, as_role, catalogue):
    b = catalogue["bottle"]
    num = pos_client.post(
        "/api/orders/confirm",
        headers=as_role("cashier", pos=True),
        json=body([{"code": b["code"], "qty": 1}]),
    ).get_json()["order"]["order_number"]
    latest = admin_client.get(f"/api/products/{b['id']}", headers=as_role("manager")).get_json()[
        "product"
    ]
    admin_client.patch(
        f"/api/products/{b['id']}",
        headers=as_role("manager"),
        json={"version": latest["version"], "market_price": "999"},
    )
    receipt = pos_client.get(
        f"/api/orders/{num}/receipt", headers=as_role("cashier", pos=True)
    ).get_json()
    assert (
        receipt["order"]["total"] == "420.00"
        and receipt["order"]["lines"][0]["unit_price"] == "420.00"
    )


@pytest.mark.parametrize(
    "overrides",
    [{"customer_name": ""}, {"customer_phone": "12345"}, {"items": []}, {"payment_mode": "cheque"}],
)
def test_confirm_validation(dbs, pos_client, as_role, catalogue, overrides):
    payload = {**body([{"code": catalogue["bottle"]["code"], "qty": 1}]), **overrides}
    assert (
        pos_client.post(
            "/api/orders/confirm", headers=as_role("cashier", pos=True), json=payload
        ).status_code
        == 400
    )


def test_reject_saves_cart_without_touching_stock(dbs, pos_client, as_role, catalogue):
    b = catalogue["bottle"]
    res = pos_client.post(
        "/api/orders/reject",
        headers=as_role("cashier", pos=True),
        json={
            "idempotency_key": str(uuid.uuid4()),
            "customer_name": "Neha",
            "discount_applied": False,
            "items": [{"code": b["code"], "qty": 3}, {"code": "P99999", "qty": 1}],
            "reason": "Customer changed mind",
        },
    )
    assert res.status_code == 201
    order = res.get_json()["order"]
    assert order["status"] == "rejected" and order["order_number"].startswith("REJ-")
    assert order["reject_reason"] == "Customer changed mind" and order["total"] == "1260.00"
    assert qty_of(dbs, b["id"]) == 4
    [audit] = dbs.scalars(select(AuditLog).where(AuditLog.action == "order.reject")).all()
    assert audit.metadata_["customer_name"] == "Neha" and audit.metadata_["skipped_codes"] == [
        "P99999"
    ]


def test_invoice_and_reject_numbers_are_separate_and_sequential(
    dbs, pos_client, as_role, catalogue
):
    h = as_role("cashier", pos=True)
    code = catalogue["notebook"]["code"]
    nums = [
        pos_client.post(
            "/api/orders/confirm", headers=h, json=body([{"code": code, "qty": 1}])
        ).get_json()["order"]["order_number"]
        for _ in range(2)
    ]
    rej = pos_client.post(
        "/api/orders/reject", headers=h, json={"idempotency_key": str(uuid.uuid4()), "items": []}
    ).get_json()["order"]["order_number"]
    assert nums[0][:13] == nums[1][:13] and int(nums[1][-4:]) == int(nums[0][-4:]) + 1
    assert rej.startswith("REJ-") and rej.endswith("-0001")


def test_invoice_numbers_restart_after_ist_midnight(dbs, pos_client, as_role, catalogue):
    code = catalogue["notebook"]["code"]
    numbers = []
    for frozen in ("2026-10-04 18:20:00", "2026-10-04 18:40:00"):  # 23:50 and 00:10 IST
        with freeze_time(frozen):
            h = as_role("cashier", pos=True)  # token minted inside the frozen clock
            res = pos_client.post(
                "/api/orders/confirm", headers=h, json=body([{"code": code, "qty": 1}])
            )
            numbers.append(res.get_json()["order"]["order_number"])
    late, early = numbers
    assert late.startswith("INV-20261004-")
    assert early == "INV-20261005-0001"


def test_receipt_access_rules(dbs, pos_client, as_role, catalogue, staff):
    num = pos_client.post(
        "/api/orders/confirm",
        headers=as_role("manager", pos=True),
        json=body([{"code": catalogue["notebook"]["code"], "qty": 1}]),
    ).get_json()["order"]["order_number"]
    # a cashier can't see someone else's order; the manager can
    assert (
        pos_client.get(
            f"/api/orders/{num}/receipt", headers=as_role("cashier", pos=True)
        ).status_code
        == 404
    )
    res = pos_client.get(f"/api/orders/{num}/receipt", headers=as_role("manager", pos=True))
    assert res.status_code == 200
    data = res.get_json()
    assert data["shop"]["name"] and set(data["order"]["lines"][0]) == {
        "code",
        "name",
        "qty",
        "unit_price",
        "line_total",
    }
    text = json.dumps(data)
    assert "cost" not in text and "profit" not in text


def test_cashier_receipt_expires_after_24h(dbs, pos_client, as_role, catalogue):
    h = as_role("cashier", pos=True)
    num = pos_client.post(
        "/api/orders/confirm",
        headers=h,
        json=body([{"code": catalogue["notebook"]["code"], "qty": 1}]),
    ).get_json()["order"]["order_number"]
    order = dbs.scalar(select(Order).where(Order.order_number == num))
    order.created_at = order.created_at - timedelta(hours=25)
    dbs.flush()
    assert pos_client.get(f"/api/orders/{num}/receipt", headers=h).status_code == 404


def test_my_orders_today(dbs, pos_client, as_role, catalogue):
    h = as_role("cashier", pos=True)
    pos_client.post(
        "/api/orders/confirm",
        headers=h,
        json=body([{"code": catalogue["notebook"]["code"], "qty": 1}]),
    )
    items = pos_client.get("/api/orders/mine", headers=h).get_json()["items"]
    assert len(items) == 1 and items[0]["total"] == "80.00"
    assert (
        pos_client.get("/api/orders/mine", headers=as_role("manager", pos=True)).get_json()["items"]
        == []
    )


# --- admin -----------------------------------------------------------------------------


def test_admin_orders_list_and_detail_with_profit(
    dbs, admin_client, pos_client, as_role, catalogue
):
    pos_client.post(
        "/api/orders/confirm",
        headers=as_role("cashier", pos=True),
        json=body([{"code": catalogue["bottle"]["code"], "qty": 2}], customer_name="Ravi"),
    )
    h = as_role("manager")
    listing = admin_client.get("/api/orders?q=ravi&status=confirmed", headers=h).get_json()
    assert listing["total"] == 1
    row = listing["items"][0]
    assert (row["total"], row["total_cost"], row["profit"]) == ("840.00", "424.00", "416.00")
    detail = admin_client.get(f"/api/orders/{row['id']}", headers=h).get_json()["order"]
    assert detail["lines"][0]["unit_cost"] == "212.00" and detail["lines"][0]["profit"] == "416.00"
    history = admin_client.get(f"/api/orders/{row['id']}/audit", headers=h).get_json()
    assert [e["action"] for e in history["items"]] == ["order.confirm"]
    assert admin_client.get("/api/orders", headers=as_role("cashier")).status_code == 403


@pytest.mark.parametrize(
    ("payload", "expected_qty"),
    [
        ({"type": "restock", "qty": 6}, 10),
        ({"type": "damage", "qty": 1, "note": "Dented"}, 3),
        ({"type": "correction", "qty": -2, "note": "Recount"}, 2),
    ],
)
def test_stock_adjustments(dbs, admin_client, as_role, catalogue, payload, expected_qty):
    b = catalogue["bottle"]
    res = admin_client.post(
        f"/api/stock/{b['id']}/adjust", headers=as_role("manager"), json=payload
    )
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["product"]["quantity"] == expected_qty
    moves = admin_client.get(
        f"/api/stock/{b['id']}/movements", headers=as_role("manager")
    ).get_json()
    assert moves["items"][0]["reason"] == payload["type"]
    audit = dbs.scalar(select(AuditLog).where(AuditLog.action == "stock.adjust"))
    assert audit.changes == {"quantity": [4, expected_qty]}


@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [
        ({"type": "damage", "qty": 5, "note": "x"}, 422, "NEGATIVE_STOCK"),
        ({"type": "damage", "qty": 1}, 400, "NOTE_REQUIRED"),
        ({"type": "restock", "qty": 0}, 400, "VALIDATION_ERROR"),
        ({"type": "correction", "qty": 0, "note": "x"}, 400, "VALIDATION_ERROR"),
    ],
)
def test_bad_stock_adjustments(dbs, admin_client, as_role, catalogue, payload, status, code):
    res = admin_client.post(
        f"/api/stock/{catalogue['bottle']['id']}/adjust", headers=as_role("manager"), json=payload
    )
    assert res.status_code == status and res.get_json()["error"]["code"] == code
    assert qty_of(dbs, catalogue["bottle"]["id"]) == 4


def test_stock_ledger_always_matches(dbs, admin_client, pos_client, as_role, catalogue):
    b = catalogue["bottle"]
    admin_client.post(
        f"/api/stock/{b['id']}/adjust",
        headers=as_role("manager"),
        json={"type": "restock", "qty": 3},
    )
    pos_client.post(
        "/api/orders/confirm",
        headers=as_role("cashier", pos=True),
        json=body([{"code": b["code"], "qty": 5}]),
    )
    res = admin_client.get("/api/stock/verify", headers=as_role("admin")).get_json()
    assert res == {"ok": True, "mismatches": []}
    assert admin_client.get("/api/stock/verify", headers=as_role("manager")).status_code == 403


def test_pos_order_payload_has_no_cost(dbs, pos_client, as_role, catalogue):
    res = pos_client.post(
        "/api/orders/confirm",
        headers=as_role("cashier", pos=True),
        json=body([{"code": catalogue["bottle"]["code"], "qty": 1}]),
    )
    text = json.dumps(res.get_json())
    assert "cost" not in text and "profit" not in text
    assert POS_FIELDS  # product shape guard lives in test_products
