import json

import pytest
from sqlalchemy import func, select

from core.models import AuditLog, Product, StockMovement
from core.schemas.orders import QuoteItem
from core.services.order_service import quote
from tests.api.test_products import create

pytestmark = pytest.mark.db


def test_quote_prices_merging_and_no_writes(dbs, client, as_role):
    headers = as_role("admin")
    bottle = create(client, headers, market_price="300", selling_price="265").get_json()["product"]
    notebook = create(
        client,
        headers,
        name="Notebook",
        cost_price="50",
        market_price="85",
        selling_price="75",
        quantity=9,
    ).get_json()["product"]
    client.post(
        "/api/pos/cart/quote",
        headers=as_role("cashier", pos=True),
        json={"items": [], "discount_applied": False},
    )
    before = [
        dbs.scalar(select(func.count()).select_from(model)) for model in (AuditLog, StockMovement)
    ]
    items = [
        {"code": bottle["code"], "qty": 2, "unit_price": "1.00"},
        {"code": notebook["code"], "qty": 1},
    ]
    for discount, total, saving in [(False, "685.00", "0.00"), (True, "605.00", "80.00")]:
        response = client.post(
            "/api/pos/cart/quote",
            headers=as_role("cashier", pos=True),
            json={"items": items, "discount_applied": discount, "total": "1.00"},
        )
        assert response.status_code == 200
        body = response.get_json()
        assert (body["subtotal_mp"], body["total"], body["discount_amount"]) == (
            "685.00",
            total,
            saving,
        )
        assert body["can_confirm"] and body["item_count"] == 3
        assert "cost" not in json.dumps(body)
    result = quote(
        [QuoteItem(code=bottle["code"], qty=2), QuoteItem(code=bottle["code"], qty=3)], False
    )
    assert len(result.lines) == 1 and result.lines[0].qty == 5
    assert result.total == "1500.00"
    assert before == [
        dbs.scalar(select(func.count()).select_from(model)) for model in (AuditLog, StockMovement)
    ]
    assert dbs.get(Product, bottle["id"]).quantity == 14


def test_quote_problem_statuses_and_empty(dbs, client, as_role):
    product = create(client, as_role("admin")).get_json()["product"]
    result = quote(
        [QuoteItem(code=product["code"], qty=20), QuoteItem(code="UNKNOWN", qty=1)], True
    )
    assert [line.status for line in result.lines] == ["insufficient_stock", "not_found"]
    assert result.lines[0].available == 14 and not result.can_confirm
    dbs.get(Product, product["id"]).is_active = False
    dbs.flush()
    assert quote([QuoteItem(code=product["code"], qty=1)], False).lines[0].status == "inactive"
    assert not quote([], False).can_confirm


@pytest.mark.parametrize("qty", [0, -1, 10001, True, 1.5, "2"])
def test_quote_rejects_invalid_quantity(dbs, client, as_role, qty):
    response = client.post(
        "/api/pos/cart/quote",
        headers=as_role("cashier", pos=True),
        json={"discount_applied": False, "items": [{"code": "P00001", "qty": qty}]},
    )
    assert response.status_code == 400


def test_quote_limits_and_unauthenticated(dbs, client, as_role):
    base = {"discount_applied": False, "items": [{"code": "P00001", "qty": 1}] * 101}
    assert (
        client.post(
            "/api/pos/cart/quote", headers=as_role("cashier", pos=True), json=base
        ).status_code
        == 400
    )
    base["items"] = [{"code": "P00001", "qty": 6000}] * 2
    assert (
        client.post(
            "/api/pos/cart/quote", headers=as_role("cashier", pos=True), json=base
        ).status_code
        == 400
    )
    assert client.post("/api/pos/cart/quote", json=base).status_code == 401


@pytest.mark.parametrize("role", ["admin", "manager", "cashier"])
def test_quote_staff_roles(dbs, client, as_role, role):
    response = client.post(
        "/api/pos/cart/quote",
        headers=as_role(role, pos=True),
        json={"discount_applied": False, "items": []},
    )
    assert response.status_code == 200


def test_quote_accepts_lowercase_codes(dbs, client, as_role):
    code = client.post(
        "/api/admin/products",
        headers=as_role("manager"),
        json={"name": "Cup", "cost_price": "50", "quantity": "3"},
    ).get_json()["product"]["code"]
    res = client.post(
        "/api/pos/cart/quote",
        headers=as_role("cashier", pos=True),
        json={"discount_applied": False, "items": [{"code": code.lower(), "qty": 1}]},
    )
    assert res.get_json()["lines"][0]["status"] == "ok"
