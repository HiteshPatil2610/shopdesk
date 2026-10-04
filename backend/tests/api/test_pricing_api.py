import pytest
from sqlalchemy import select

from core.models import AuditLog

pytestmark = pytest.mark.db

SETTINGS = {
    "markup_low_pct": "95",
    "markup_high_pct": "90",
    "markup_threshold": "500",
    "small_mp_limit": "500",
    "small_mp_step": "10",
    "small_mp_alt_step": "50",
    "mp_step": "50",
    "mp_alt_step": "100",
    "sp_discount_pct": "10",
    "sp_step": "10",
}


def test_preview_returns_both_mp_options(dbs, admin_client, as_role):
    res = admin_client.post(
        "/api/pricing/preview", headers=as_role("manager"), json={"cost_price": "743"}
    )
    body = res.get_json()
    assert res.status_code == 200
    assert body["raw_market_price"] == "1411.70"
    assert [o["value"] for o in body["mp_options"]] == ["1450.00", "1500.00"]
    assert (body["market_price"], body["selling_price"]) == ("1450.00", "1300.00")
    assert "₹50" in body["explanation"]


def test_preview_with_unsaved_settings(dbs, admin_client, as_role):
    custom = {**SETTINGS, "markup_high_pct": "100"}
    res = admin_client.post(
        "/api/pricing/preview",
        headers=as_role("admin"),
        json={"cost_price": "1000", "settings": custom},
    )
    assert res.get_json()["market_price"] == "2000.00"


def test_settings_get_and_admin_only_put(dbs, admin_client, as_role):
    got = admin_client.get("/api/pricing/settings", headers=as_role("manager")).get_json()[
        "settings"
    ]
    assert got["markup_low_pct"] == "95.00" and got["sp_step"] == "10.00"
    assert (
        admin_client.put(
            "/api/pricing/settings", headers=as_role("manager"), json=SETTINGS
        ).status_code
        == 403
    )
    res = admin_client.put(
        "/api/pricing/settings", headers=as_role("admin"), json={**SETTINGS, "sp_step": "100"}
    )
    assert res.status_code == 200 and res.get_json()["settings"]["sp_step"] == "100.00"
    audit = dbs.scalar(select(AuditLog).where(AuditLog.action == "pricing_settings.update"))
    assert audit.changes == {"sp_step": ["10.00", "100.00"]}


def test_bad_settings_rejected(dbs, admin_client, as_role):
    h = as_role("admin")
    assert (
        admin_client.put(
            "/api/pricing/settings", headers=h, json={**SETTINGS, "mp_step": "0"}
        ).status_code
        == 400
    )
    res = admin_client.put(
        "/api/pricing/settings", headers=h, json={**SETTINGS, "mp_alt_step": "20"}
    )
    assert res.status_code == 422


def test_settings_change_does_not_reprice_until_apply(dbs, admin_client, as_role):
    h = as_role("admin")
    pid = admin_client.post(
        "/api/products", headers=h, json={"name": "Bottle", "cost_price": "650", "quantity": "1"}
    ).get_json()["product"]["id"]
    manual = admin_client.post(
        "/api/products",
        headers=h,
        json={
            "name": "Fixed",
            "cost_price": "650",
            "quantity": "1",
            "market_price": "2000",
            "selling_price": "1800",
        },
    ).get_json()["product"]["id"]
    admin_client.put(
        "/api/pricing/settings", headers=h, json={**SETTINGS, "markup_high_pct": "100"}
    )
    assert (
        admin_client.get(f"/api/products/{pid}", headers=h).get_json()["product"]["market_price"]
        == "1250.00"
    )  # PE-4

    dry = admin_client.post("/api/pricing/apply", headers=h, json={"dry_run": True}).get_json()
    assert dry["affected"] == 1 and dry["applied"] is False
    assert (
        admin_client.get(f"/api/products/{pid}", headers=h).get_json()["product"]["market_price"]
        == "1250.00"
    )

    real = admin_client.post("/api/pricing/apply", headers=h, json={"dry_run": False}).get_json()
    assert real["affected"] == 1 and real["applied"] is True
    product = admin_client.get(f"/api/products/{pid}", headers=h).get_json()["product"]
    assert (product["market_price"], product["selling_price"]) == ("1300.00", "1170.00")
    assert (
        admin_client.get(f"/api/products/{manual}", headers=h).get_json()["product"]["market_price"]
        == "2000.00"
    )
    actions = dbs.scalars(
        select(AuditLog.action).where(AuditLog.action.in_(["product.reprice", "pricing.apply"]))
    ).all()
    assert sorted(actions) == ["pricing.apply", "product.reprice"]


def test_manager_cannot_apply(dbs, admin_client, as_role):
    assert (
        admin_client.post("/api/pricing/apply", headers=as_role("manager"), json={}).status_code
        == 403
    )
