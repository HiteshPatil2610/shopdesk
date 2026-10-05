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
    "sp_avoid_ten": True,
}


def test_preview_returns_both_mp_options(dbs, client, as_role):
    res = client.post(
        "/api/admin/pricing/preview", headers=as_role("manager"), json={"cost_price": "743"}
    )
    body = res.get_json()
    assert res.status_code == 200
    assert body["raw_market_price"] == "1411.70"
    assert [o["value"] for o in body["mp_options"]] == ["1450.00", "1500.00"]
    assert (body["market_price"], body["selling_price"]) == ("1450.00", "1300.00")
    assert "₹50" in body["explanation"]


def test_preview_with_unsaved_settings(dbs, client, as_role):
    custom = {**SETTINGS, "markup_high_pct": "100"}
    res = client.post(
        "/api/admin/pricing/preview",
        headers=as_role("admin"),
        json={"cost_price": "1000", "settings": custom},
    )
    assert res.get_json()["market_price"] == "2000.00"


def test_settings_get_and_admin_only_put(dbs, client, as_role):
    got = client.get("/api/admin/pricing/settings", headers=as_role("manager")).get_json()[
        "settings"
    ]
    assert got["markup_low_pct"] == "95.00" and got["sp_step"] == "10.00"
    assert (
        client.put(
            "/api/admin/pricing/settings", headers=as_role("manager"), json=SETTINGS
        ).status_code
        == 403
    )
    res = client.put(
        "/api/admin/pricing/settings", headers=as_role("admin"), json={**SETTINGS, "sp_step": "100"}
    )
    assert res.status_code == 200 and res.get_json()["settings"]["sp_step"] == "100.00"
    audit = dbs.scalar(select(AuditLog).where(AuditLog.action == "pricing_settings.update"))
    assert audit.changes == {"sp_step": ["10.00", "100.00"]}


def test_bad_settings_rejected(dbs, client, as_role):
    h = as_role("admin")
    assert (
        client.put(
            "/api/admin/pricing/settings", headers=h, json={**SETTINGS, "mp_step": "0"}
        ).status_code
        == 400
    )
    res = client.put(
        "/api/admin/pricing/settings", headers=h, json={**SETTINGS, "mp_alt_step": "20"}
    )
    assert res.status_code == 422


def test_sp_rounding_switch_is_saved_audited_and_used(dbs, client, as_role):
    h = as_role("admin")
    before = client.post("/api/admin/pricing/preview", headers=h, json={"cost_price": "700"})
    assert before.get_json()["selling_price"] == "1200.00"
    res = client.put(
        "/api/admin/pricing/settings", headers=h, json={**SETTINGS, "sp_avoid_ten": False}
    )
    assert res.status_code == 200
    assert res.get_json()["settings"]["sp_avoid_ten"] is False
    after = client.post("/api/admin/pricing/preview", headers=h, json={"cost_price": "700"})
    assert after.get_json()["selling_price"] == "1210.00"
    audit = dbs.scalar(select(AuditLog).where(AuditLog.action == "pricing_settings.update"))
    assert audit.changes == {"sp_avoid_ten": [True, False]}


def test_settings_change_does_not_reprice_until_apply(dbs, client, as_role):
    h = as_role("admin")
    pid = client.post(
        "/api/admin/products",
        headers=h,
        json={"name": "Bottle", "cost_price": "650", "quantity": "1"},
    ).get_json()["product"]["id"]
    manual = client.post(
        "/api/admin/products",
        headers=h,
        json={
            "name": "Fixed",
            "cost_price": "650",
            "quantity": "1",
            "market_price": "2000",
            "selling_price": "1800",
        },
    ).get_json()["product"]["id"]
    client.put(
        "/api/admin/pricing/settings", headers=h, json={**SETTINGS, "markup_high_pct": "100"}
    )
    assert (
        client.get(f"/api/admin/products/{pid}", headers=h).get_json()["product"]["market_price"]
        == "1250.00"
    )  # PE-4

    dry = client.post("/api/admin/pricing/apply", headers=h, json={"dry_run": True}).get_json()
    assert dry["affected"] == 1 and dry["applied"] is False
    assert (
        client.get(f"/api/admin/products/{pid}", headers=h).get_json()["product"]["market_price"]
        == "1250.00"
    )

    real = client.post("/api/admin/pricing/apply", headers=h, json={"dry_run": False}).get_json()
    assert real["affected"] == 1 and real["applied"] is True
    product = client.get(f"/api/admin/products/{pid}", headers=h).get_json()["product"]
    assert (product["market_price"], product["selling_price"]) == (
        "1300.00",
        "1170.00",
    )  # 1170: tens digit 7
    assert (
        client.get(f"/api/admin/products/{manual}", headers=h).get_json()["product"]["market_price"]
        == "2000.00"
    )
    actions = dbs.scalars(
        select(AuditLog.action).where(AuditLog.action.in_(["product.reprice", "pricing.apply"]))
    ).all()
    assert sorted(actions) == ["pricing.apply", "product.reprice"]


def test_manager_cannot_apply(dbs, client, as_role):
    assert (
        client.post("/api/admin/pricing/apply", headers=as_role("manager"), json={}).status_code
        == 403
    )


def test_preview_with_manual_mp_returns_matching_sp(dbs, client, as_role):
    res = client.post(
        "/api/admin/pricing/preview",
        headers=as_role("manager"),
        json={"cost_price": "743", "market_price": "1293"},
    )
    body = res.get_json()
    assert (body["market_price"], body["selling_price"]) == ("1293.00", "1160.00")
    assert body["manual_market_price"] is True


def test_preview_manual_mp_below_cost_has_no_sp(dbs, client, as_role):
    res = client.post(
        "/api/admin/pricing/preview",
        headers=as_role("manager"),
        json={"cost_price": "743", "market_price": "500"},
    )
    assert res.get_json()["selling_price"] is None
