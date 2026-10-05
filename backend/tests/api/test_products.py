import io
import json

import pytest
from sqlalchemy import func, select

from core.models import AuditLog, Product, StockMovement
from core.serializers import POS_FIELDS
from tests.conftest import png_bytes

pytestmark = pytest.mark.db


def create(client, headers, **overrides):
    payload = {"name": "Steel bottle", "cost_price": "212.00", "quantity": "14"}
    payload.update(overrides)
    return client.post("/api/admin/products", headers=headers, json=payload)


def audits(dbs, action):
    return dbs.scalars(select(AuditLog).where(AuditLog.action == action)).all()


# --- create ---------------------------------------------------------------------------


def test_create_auto_prices_code_stock_and_audit(dbs, client, as_role):
    res = create(client, as_role("manager"))
    assert res.status_code == 201, res.get_json()
    p = res.get_json()["product"]
    # Owner's formula: 212 + 95% = 413.40 → up to ₹10 = 420; SP = 378 → down to ₹10 = 370
    assert (p["market_price"], p["selling_price"]) == ("420.00", "370.00")
    assert p["mp_is_manual"] is False and p["sp_is_manual"] is False
    assert p["code"].startswith("P") and len(p["code"]) == 6
    assert p["quantity"] == 14 and p["version"] == 1
    moves = dbs.scalars(select(StockMovement).where(StockMovement.product_id == p["id"])).all()
    assert [(m.change, m.reason, m.quantity_after) for m in moves] == [(14, "initial", 14)]
    [audit] = audits(dbs, "product.create")
    assert audit.actor_username == "manager" and audit.source == "admin"


def test_create_with_alternate_rounding(dbs, client, as_role):
    res = create(client, as_role("manager"), cost_price="743", mp_round_mode="alternate")
    p = res.get_json()["product"]
    assert (p["market_price"], p["selling_price"]) == ("1500.00", "1350.00")


def test_manual_prices_are_kept_and_flagged(dbs, client, as_role):
    res = create(client, as_role("manager"), market_price="500", selling_price="400")
    p = res.get_json()["product"]
    assert (p["market_price"], p["selling_price"], p["mp_is_manual"], p["sp_is_manual"]) == (
        "500.00",
        "400.00",
        True,
        True,
    )


def test_manual_mp_drives_auto_sp(dbs, client, as_role):
    p = create(client, as_role("manager"), market_price="1293").get_json()["product"]
    assert p["selling_price"] == "1160.00"  # 1163.70 → down to ₹10


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"selling_price": "100"}, "below cost"),
        ({"market_price": "300", "selling_price": "350"}, "above"),
    ],
)
def test_price_rule_violations_are_422(dbs, client, as_role, overrides, message):
    res = create(client, as_role("manager"), **overrides)
    assert res.status_code == 422
    assert message in res.get_json()["error"]["message"]
    assert dbs.scalar(select(func.count()).select_from(Product)) == 0


def test_float_money_is_rejected(dbs, client, as_role):
    res = client.post(
        "/api/admin/products",
        headers=as_role("manager"),
        json={"name": "X1", "cost_price": 10.5, "quantity": 1},
    )
    assert res.status_code == 400


def test_duplicate_barcode_is_409(dbs, client, as_role):
    create(client, as_role("manager"), barcode="8901234567890")
    res = create(client, as_role("manager"), name="Other", barcode="8901234567890")
    assert res.status_code == 409 and res.get_json()["error"]["code"] == "BARCODE_TAKEN"


def test_codes_are_sequential(dbs, client, as_role):
    a = create(client, as_role("manager")).get_json()["product"]["code"]
    b = create(client, as_role("manager"), name="Lunch box").get_json()["product"]["code"]
    assert int(b[1:]) == int(a[1:]) + 1


# --- images ---------------------------------------------------------------------------


def test_create_with_image_multipart(dbs, client, as_role, fake_media):
    data = {
        "name": "Notebook A5",
        "cost_price": "40",
        "quantity": "9",
        "image": (io.BytesIO(png_bytes()), "n.png"),
    }
    res = client.post(
        "/api/admin/products",
        headers=as_role("manager"),
        data=data,
        content_type="multipart/form-data",
    )
    assert res.status_code == 201, res.get_json()
    p = res.get_json()["product"]
    assert fake_media.uploads and fake_media.uploads[0][0].endswith("img1")
    assert "res.cloudinary.com" in (p["thumb_url"] or "") or p["thumb_url"] is None


def test_fake_image_is_415_and_nothing_saved(dbs, client, as_role, fake_media):
    data = {
        "name": "Bad",
        "cost_price": "40",
        "quantity": "1",
        "image": (io.BytesIO(b"not an image"), "x.png"),
    }
    res = client.post(
        "/api/admin/products",
        headers=as_role("manager"),
        data=data,
        content_type="multipart/form-data",
    )
    assert res.status_code == 415
    assert fake_media.uploads == []


def test_db_failure_after_upload_deletes_the_image(dbs, client, as_role, fake_media, monkeypatch):
    from core.services import stock_service

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(stock_service, "record_initial", boom)
    data = {
        "name": "Boom",
        "cost_price": "40",
        "quantity": "1",
        "image": (io.BytesIO(png_bytes()), "b.png"),
    }
    res = client.post(
        "/api/admin/products",
        headers=as_role("manager"),
        data=data,
        content_type="multipart/form-data",
    )
    assert res.status_code == 500
    assert fake_media.deleted == [fake_media.uploads[0][0]]


def test_replace_image_deletes_old_after_commit(dbs, client, as_role, fake_media):
    pid = create(client, as_role("manager")).get_json()["product"]["id"]
    for name in ("a.png", "b.png"):
        client.post(
            f"/api/admin/products/{pid}/image",
            headers=as_role("manager"),
            data={"image": (io.BytesIO(png_bytes()), name)},
            content_type="multipart/form-data",
        )
    assert fake_media.deleted == [fake_media.uploads[0][0]]
    assert len(audits(dbs, "product.image_update")) == 2


# --- update ---------------------------------------------------------------------------


def test_edit_mp_marks_manual_and_cost_change_keeps_it(dbs, client, as_role):
    h = as_role("manager")
    p = create(client, h).get_json()["product"]
    p = client.patch(
        f"/api/admin/products/{p['id']}",
        headers=h,
        json={"version": p["version"], "market_price": "450"},
    ).get_json()["product"]
    assert (p["market_price"], p["mp_is_manual"], p["selling_price"]) == ("450.00", True, "400.00")
    p = client.patch(
        f"/api/admin/products/{p['id']}",
        headers=h,
        json={"version": p["version"], "cost_price": "230"},
    ).get_json()["product"]
    assert p["market_price"] == "450.00"  # manual MP kept
    assert p["selling_price"] == "400.00"  # SP follows MP (405 → 400)
    [audit] = [a for a in audits(dbs, "product.update") if "cost_price" in (a.changes or {})]
    assert audit.changes["cost_price"] == ["212.00", "230.00"]


def test_cost_change_reprices_auto_prices(dbs, client, as_role):
    h = as_role("manager")
    p = create(client, h).get_json()["product"]
    p = client.patch(
        f"/api/admin/products/{p['id']}", headers=h, json={"version": 1, "cost_price": "650"}
    ).get_json()["product"]
    assert (p["market_price"], p["selling_price"]) == ("1250.00", "1120.00")


def test_version_conflict(dbs, client, as_role):
    h = as_role("manager")
    p = create(client, h).get_json()["product"]
    client.patch(
        f"/api/admin/products/{p['id']}", headers=h, json={"version": 1, "name": "Steel bottle 1L"}
    )
    res = client.patch(
        f"/api/admin/products/{p['id']}", headers=h, json={"version": 1, "name": "Late edit"}
    )
    assert res.status_code == 409
    body = res.get_json()["error"]
    assert body["code"] == "VERSION_CONFLICT" and body["details"]["current_version"] == 2


def test_quantity_cannot_be_patched(dbs, client, as_role):
    h = as_role("manager")
    p = create(client, h).get_json()["product"]
    res = client.patch(
        f"/api/admin/products/{p['id']}", headers=h, json={"version": 1, "quantity": 99}
    )
    assert res.status_code == 400 and res.get_json()["error"]["code"] == "USE_STOCK_ADJUSTMENT"


def test_sp_above_mp_on_edit_is_422(dbs, client, as_role):
    h = as_role("manager")
    p = create(client, h).get_json()["product"]
    res = client.patch(
        f"/api/admin/products/{p['id']}", headers=h, json={"version": 1, "selling_price": "999"}
    )
    assert res.status_code == 422


def test_reset_to_auto(dbs, client, as_role):
    h = as_role("manager")
    p = create(client, h, market_price="999").get_json()["product"]
    res = client.post(
        f"/api/admin/products/{p['id']}/recalculate-prices",
        headers=h,
        json={"version": p["version"], "reset_manual": True},
    )
    p = res.get_json()["product"]
    assert (p["market_price"], p["mp_is_manual"]) == ("420.00", False)


# --- deactivate / list / roles ----------------------------------------------------------


def test_deactivated_products_hidden_from_pos(dbs, client, as_role):
    h = as_role("manager")
    p = create(client, h).get_json()["product"]
    client.post(f"/api/admin/products/{p['id']}/deactivate", headers=h)
    pos = as_role("cashier", pos=True)
    assert client.get("/api/pos/products", headers=pos).get_json()["total"] == 0
    assert client.get(f"/api/pos/products/lookup?code={p['code']}", headers=pos).status_code == 404
    admin_list = client.get("/api/admin/products?include_inactive=true", headers=h).get_json()
    assert admin_list["total"] == 1 and admin_list["items"][0]["is_active"] is False
    assert len(audits(dbs, "product.deactivate")) == 1


def test_list_search_filter_and_paging(dbs, client, as_role):
    h = as_role("manager")
    for i, name in enumerate(["Steel bottle", "Lunch box", "Steel plate"]):
        create(client, h, name=name, quantity=str(i))
    res = client.get("/api/admin/products?search=steel&sort=name&page_size=1", headers=h).get_json()
    assert (
        res["total"] == 2 and len(res["items"]) == 1 and res["items"][0]["name"] == "Steel bottle"
    )
    low = client.get("/api/admin/products?low_stock=true", headers=h).get_json()
    assert low["total"] == 3  # qty 0,1,2 ≤ reorder level 5


def test_pos_never_sees_cost_or_margins(dbs, client, as_role):
    p = create(client, as_role("manager"), barcode="890111").get_json()["product"]
    pos = as_role("cashier", pos=True)
    listed = client.get("/api/pos/products", headers=pos).get_json()["items"][0]
    looked_up = client.get("/api/pos/products/lookup?code=890111", headers=pos).get_json()[
        "product"
    ]
    for item in (listed, looked_up):
        assert set(item) == POS_FIELDS
        text = json.dumps(item)
        assert "cost" not in text and "margin" not in text
    lower = client.get(f"/api/pos/products/lookup?code={p['code'].lower()}", headers=pos)
    assert lower.status_code == 200


def test_cashier_cannot_use_admin_product_api(dbs, client, as_role):
    res = client.get("/api/admin/products", headers=as_role("cashier"))
    assert res.status_code == 403


def test_categories(dbs, client, as_role):
    h = as_role("manager")
    cat = client.post("/api/admin/categories", headers=h, json={"name": "Kitchen"}).get_json()[
        "category"
    ]
    assert (
        client.post("/api/admin/categories", headers=h, json={"name": "kitchen"}).status_code == 409
    )
    p = create(client, h, category_id=str(cat["id"])).get_json()["product"]
    assert p["category"]["name"] == "Kitchen"
    assert create(client, h, name="X2", category_id="999999").status_code == 400
