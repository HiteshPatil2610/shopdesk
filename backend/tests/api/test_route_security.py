"""Default deny and area boundaries, across the complete registered route map."""

import re

import pytest
from flask import jsonify
from sqlalchemy import select

from core.models import AuditLog
from core.security import require_role
from shopdesk.areas import AREA_ROLES, AreaBlueprint

PUBLIC_ALLOWLIST = {"/api/health", "/api/webhooks/clerk"}


def test_every_route_has_a_guard_and_area(app):
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        assert rule.rule.startswith(
            ("/api/admin/", "/api/pos/", "/api/auth/", "/api/health", "/api/webhooks/")
        )
        view = app.view_functions[rule.endpoint]
        if getattr(view, "_shopdesk_public", False):
            assert rule.rule in PUBLIC_ALLOWLIST
        else:
            assert getattr(view, "_shopdesk_roles", None)
        for area in AREA_ROLES:
            if rule.rule.startswith(f"/api/{area}/"):
                bp = app.blueprints[rule.endpoint.split(".")[0]]
                assert isinstance(bp, AreaBlueprint) and bp.shopdesk_area == area
                if area == "admin":
                    assert "cashier" not in view._shopdesk_roles


def route_path(rule):
    return re.sub(r"<(?:(?:int|path):)?([^>]+)>", "1", rule.rule)


@pytest.mark.db
def test_every_admin_method_refuses_cashier_with_audit(dbs, app, client, as_role):
    rules = [r for r in app.url_map.iter_rules() if r.rule.startswith("/api/admin/")]
    assert rules
    for rule in rules:
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            response = client.open(
                route_path(rule), method=method, headers=as_role("cashier"), json={}
            )
            assert response.status_code == 403, (rule.rule, method, response.get_json())
            assert response.get_json()["error"]["code"] == "ROLE_NOT_ALLOWED"
    denied = dbs.scalars(select(AuditLog).where(AuditLog.action == "auth.role_denied")).all()
    assert denied and all(row.source == "admin" for row in denied)


@pytest.mark.db
@pytest.mark.parametrize("area", ["admin", "pos"])
def test_wrong_origin_rejected_in_each_area(dbs, client, auth_header, area):
    response = client.get(f"/api/{area}/products", headers=auth_header(azp="https://other.example"))
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "TOKEN_WRONG_APP"


def test_guard_fails_closed_without_area(app):
    app.add_url_rule(
        "/api/admin/unassigned", view_func=require_role("admin")(lambda: jsonify({"ok": True}))
    )
    response = app.test_client().get("/api/admin/unassigned")
    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == "INTERNAL_ERROR"


@pytest.mark.db
def test_every_pos_route_valid_response_is_cost_free(dbs, app, client, as_role):
    from tests.api.test_orders import body
    from tests.api.test_products import create

    product = create(client, as_role("admin"), quantity=20).get_json()["product"]
    headers = as_role("cashier")
    bill = body([{"code": product["code"], "qty": 1}], discount_applied=True)
    confirmed = client.post("/api/pos/orders/confirm", headers=headers, json=bill)
    assert confirmed.status_code == 201
    number = confirmed.get_json()["order"]["order_number"]
    requests = {
        "pos_products.list_products": ("GET", "/api/pos/products", {}),
        "pos_products.lookup": (
            "GET",
            "/api/pos/products/lookup",
            {"query_string": {"code": product["code"]}},
        ),
        "pos_cart.quote": ("POST", "/api/pos/cart/quote", {"json": bill}),
        "pos_orders.confirm": ("POST", "/api/pos/orders/confirm", {"json": bill}),
        "pos_orders.reject": (
            "POST",
            "/api/pos/orders/reject",
            {"json": body([{"code": product["code"], "qty": 1}])},
        ),
        "pos_orders.receipt": ("GET", f"/api/pos/orders/{number}/receipt", {}),
        "pos_orders.mine": ("GET", "/api/pos/orders/mine", {}),
    }

    def scan(value):
        if isinstance(value, dict):
            for key, child in value.items():
                assert not any(word in key.lower() for word in ("cost", "profit", "margin")), key
                scan(child)
        elif isinstance(value, list):
            for child in value:
                scan(child)

    registered = {r.endpoint for r in app.url_map.iter_rules() if r.rule.startswith("/api/pos/")}
    assert registered == requests.keys(), "A new POS route needs a valid-data cost-leak test"
    for endpoint, (method, path, kwargs) in requests.items():
        response = client.open(path, method=method, headers=headers, **kwargs)
        assert response.status_code in {200, 201}, (endpoint, response.get_json())
        scan(response.get_json())


@pytest.mark.db
def test_three_megabyte_valid_image_reaches_upload(dbs, client, as_role, fake_media):
    import io

    from PIL import Image

    from tests.api.test_products import create

    product = create(client, as_role("admin")).get_json()["product"]
    buf = io.BytesIO()
    Image.new("RGB", (1024, 1024), "red").save(buf, "PNG", compress_level=0)
    assert 3 * 1024 * 1024 < len(buf.getvalue()) < 4 * 1024 * 1024
    buf.seek(0)
    response = client.post(
        f"/api/admin/products/{product['id']}/image",
        headers=as_role("admin"),
        data={"image": (buf, "photo.png")},
    )
    assert response.status_code == 200, response.get_json()
    assert fake_media.uploads
