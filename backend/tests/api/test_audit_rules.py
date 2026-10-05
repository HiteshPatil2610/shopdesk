"""Spec 05 acceptance rules that cut across features (AL-1, AL-2)."""

import json

import pytest
from sqlalchemy import func, select

from core.models import AuditLog

pytestmark = pytest.mark.db


def make_product(client, headers, **overrides):
    payload = {"name": "Steel bottle", "cost_price": "212", "quantity": "5"}
    payload.update(overrides)
    return client.post("/api/admin/products", headers=headers, json=payload).get_json()["product"]


def test_mp_change_writes_one_precise_update_row(dbs, client, as_role):
    h = {**as_role("manager"), "X-Forwarded-For": "203.0.113.7", "User-Agent": "pytest-agent"}
    p = make_product(client, h, market_price="300", selling_price="250")
    client.patch(
        f"/api/admin/products/{p['id']}",
        headers=h,
        json={"version": p["version"], "market_price": "320"},
    )
    rows = dbs.scalars(select(AuditLog).where(AuditLog.action == "product.update")).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.changes == {"market_price": ["300.00", "320.00"]}
    assert (row.actor_username, row.source) == ("manager", "admin")
    assert str(row.ip_address) == "203.0.113.7" and row.user_agent == "pytest-agent"


def test_rejected_update_writes_no_audit_row(dbs, client, as_role):
    h = as_role("manager")
    p = make_product(client, h)
    before = dbs.scalar(select(func.count()).select_from(AuditLog))
    res = client.patch(
        f"/api/admin/products/{p['id']}", headers=h, json={"version": 1, "selling_price": "1"}
    )
    assert res.status_code == 422  # BR-2: SP below cost
    assert dbs.scalar(select(func.count()).select_from(AuditLog)) == before


def test_passwords_never_reach_the_audit_log(dbs, client, as_role, fake_clerk):
    h = as_role("admin")
    created = client.post(
        "/api/admin/users",
        headers=h,
        json={
            "username": "ravi",
            "full_name": "Ravi K",
            "role": "cashier",
            "password": "Very-secret-pass-1",
        },
    ).get_json()["user"]
    client.post(
        f"/api/admin/users/{created['id']}/reset-password",
        headers=h,
        json={"new_password": "Another-secret-2"},
    )
    everything = json.dumps(
        [[r.summary, r.changes, r.metadata_] for r in dbs.scalars(select(AuditLog)).all()]
    )
    assert "Very-secret-pass-1" not in everything and "Another-secret-2" not in everything
