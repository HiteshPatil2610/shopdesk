import csv
import io

import pytest
from sqlalchemy import func, select

from core.actor import ActorContext
from core.models import AuditLog
from core.pricing import PricingRules
from core.services import audit_service
from core.services.pricing_service import settings_out

pytestmark = pytest.mark.db


@pytest.fixture()
def entries(dbs):
    first = audit_service.record(
        ActorContext.system(),
        "product.update",
        "product",
        42,
        '=HYPERLINK("example")',
        changes={"market_price": ["300.00", "320.00"]},
    )
    second = audit_service.record(ActorContext.system(), "user.create", "user", 7, "Created staff")
    dbs.flush()
    return first, second


def test_filters_pagination_and_details(dbs, client, as_role, entries):
    first, _ = entries
    response = client.get(
        "/api/admin/audit-logs?action=product.&entity_id=42&source=system&page_size=1",
        headers=as_role("manager"),
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["total"] == 1 and body["items"][0]["id"] == first.id
    detail = client.get(f"/api/admin/audit-logs/{first.id}", headers=as_role("manager"))
    assert detail.get_json()["entry"]["changes"] == {"market_price": ["300.00", "320.00"]}
    empty = client.get("/api/admin/audit-logs?q=missing", headers=as_role("admin"))
    assert empty.get_json()["items"] == []


def test_csv_is_safe_and_export_is_audited(dbs, client, as_role, entries):
    response = client.get(
        "/api/admin/audit-logs/export.csv?action=product.", headers=as_role("admin")
    )
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))
    assert len(rows) == 1 and rows[0]["summary"].startswith("'=HYPERLINK")
    event = dbs.scalar(select(AuditLog).where(AuditLog.action == "audit.export"))
    assert event.metadata_["row_count"] == 1
    assert event.metadata_["filters"]["action"] == "product."


def test_permissions_and_read_only_routes(dbs, client, as_role):
    assert client.get("/api/admin/audit-logs", headers=as_role("cashier")).status_code == 403
    assert (
        client.get("/api/admin/audit-logs/export.csv", headers=as_role("manager")).status_code
        == 403
    )
    for method in ("post", "patch", "delete"):
        assert (
            getattr(client, method)("/api/admin/audit-logs/1", headers=as_role("admin")).status_code
            == 405
        )


@pytest.mark.parametrize(
    "query",
    ["page=0", "page_size=101", "source=unknown", "from=bad", "from=2026-10-05&to=2026-10-04"],
)
def test_bad_filters_are_rejected(dbs, client, as_role, query):
    assert client.get(f"/api/admin/audit-logs?{query}", headers=as_role("admin")).status_code == 400


def test_missing_entry_and_product_history(dbs, client, as_role):
    headers = as_role("manager")
    assert client.get("/api/admin/audit-logs/999999", headers=headers).status_code == 404
    product = client.post(
        "/api/admin/products",
        headers=headers,
        json={"name": "Bottle", "quantity": 1, "cost_price": "212"},
    ).get_json()["product"]
    rows = client.get(f"/api/admin/products/{product['id']}/audit", headers=headers).get_json()[
        "items"
    ]
    assert len(rows) == 1 and rows[0]["action"] == "product.create"


def test_existing_catalogue_and_staff_writes_append_audit_entries(dbs, client, as_role, fake_clerk):
    """Exercise the built write flows and require an audit event after each success."""
    headers = as_role("admin")

    def write(method, url, payload=None):
        before = dbs.scalar(select(func.count()).select_from(AuditLog))
        response = getattr(client, method)(url, headers=headers, json=payload)
        assert response.status_code < 300, response.get_json()
        # Consume streamed exports before making the next query.
        response.get_data()
        assert dbs.scalar(select(func.count()).select_from(AuditLog)) > before
        return response.get_json() if response.is_json else None

    write("post", "/api/admin/categories", {"name": "Kitchen"})
    product = write(
        "post", "/api/admin/products", {"name": "Bottle", "quantity": 2, "cost_price": "212"}
    )["product"]
    write(
        "patch",
        f"/api/admin/products/{product['id']}",
        {"version": product["version"], "name": "Steel bottle"},
    )
    write("post", f"/api/admin/products/{product['id']}/deactivate")
    write("post", f"/api/admin/products/{product['id']}/activate")
    settings = {**settings_out(PricingRules()), "markup_low_pct": "100"}
    write("put", "/api/admin/pricing/settings", settings)
    write("post", "/api/admin/pricing/apply", {"dry_run": False})
    user = write(
        "post",
        "/api/admin/users",
        {
            "username": "priya",
            "full_name": "Priya Shah",
            "role": "cashier",
            "password": "test-counter-pass",
        },
    )["user"]
    write("patch", f"/api/admin/users/{user['id']}", {"full_name": "Priya S"})
    write(
        "post",
        f"/api/admin/users/{user['id']}/reset-password",
        {"new_password": "new-counter-pass"},
    )
    write("post", f"/api/admin/users/{user['id']}/ban")
    write("post", f"/api/admin/users/{user['id']}/unban")
    write("get", "/api/admin/audit-logs/export.csv")
