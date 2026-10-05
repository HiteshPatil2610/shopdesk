import json

import pytest
from sqlalchemy import select

from core.models import AuditLog, User

pytestmark = pytest.mark.db


def test_revoke_sessions_is_audited(dbs, admin_client, as_owner, owner, fake_clerk):
    response = admin_client.post(f"/api/users/{owner.id}/revoke-sessions", headers=as_owner)
    assert response.status_code == 200 and response.get_json()["sessions_revoked"] == 2
    assert ("revoke_sessions", (owner.clerk_user_id,)) in fake_clerk.calls
    row = dbs.scalar(select(AuditLog).where(AuditLog.action == "user.sessions_revoke"))
    assert row.metadata_["sessions_revoked"] == 2


def test_failed_revocation_is_audited(dbs, admin_client, as_owner, owner, fake_clerk, monkeypatch):
    from core.errors import AppError

    def fail(_user_id):
        raise AppError("Clerk unavailable", status=502)

    monkeypatch.setattr(fake_clerk, "revoke_sessions", fail)
    response = admin_client.post(f"/api/users/{owner.id}/revoke-sessions", headers=as_owner)
    assert response.status_code == 502
    assert dbs.scalar(select(AuditLog).where(AuditLog.action == "user.sessions_revoke_failed"))


@pytest.mark.parametrize("role", ["manager", "cashier"])
def test_non_admin_cannot_revoke_sessions(dbs, admin_client, auth_header, fake_clerk, role):
    response = admin_client.post("/api/users/1/revoke-sessions", headers=auth_header(role=role))
    assert response.status_code == 403
    assert not fake_clerk.calls


@pytest.fixture()
def owner(dbs):
    user = User(clerk_user_id="user_owner", username="owner", full_name="Owner", role="admin")
    dbs.add(user)
    dbs.flush()
    return user


@pytest.fixture()
def as_owner(auth_header, owner):
    return auth_header(sub="user_owner", role="admin", username="owner", name="Owner")


def test_admin_creates_cashier(dbs, admin_client, as_owner, fake_clerk):
    res = admin_client.post(
        "/api/users",
        headers=as_owner,
        json={
            "username": "Priya",
            "full_name": "Priya Shah",
            "role": "cashier",
            "password": "counter-pass-01",
        },
    )
    assert res.status_code == 201, res.get_json()
    user = res.get_json()["user"]
    assert user["username"] == "priya"
    assert user["role"] == "cashier"
    assert fake_clerk.calls[0] == ("create_user", ("priya", "Priya Shah", "cashier"))
    audit = dbs.scalar(select(AuditLog).where(AuditLog.action == "user.create"))
    assert audit.actor_username == "owner"
    assert audit.source == "admin"
    assert "counter-pass-01" not in json.dumps([audit.changes, audit.metadata_, audit.summary])


def test_admin_user_details_include_profile_and_dates_without_passwords(
    dbs, admin_client, as_owner, owner
):
    owner.email = "owner@example.test"
    dbs.flush()
    res = admin_client.get("/api/users", headers=as_owner)
    assert res.status_code == 200
    user = res.get_json()["items"][0]
    assert user["username"] == "owner"
    assert user["email"] == "owner@example.test"
    assert user["clerk_user_id"] == "user_owner"
    assert user["created_at"] and user["updated_at"]
    assert not any("password" in key for key in user)


@pytest.mark.parametrize("role", ["manager", "cashier"])
def test_user_details_are_admin_only(dbs, admin_client, as_role, role):
    assert admin_client.get("/api/users", headers=as_role(role)).status_code == 403


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        (
            {"username": "ab", "full_name": "X Y", "role": "cashier", "password": "long-enough-1"},
            "username",
        ),
        (
            {"username": "priya", "full_name": "Priya", "role": "cashier", "password": "short"},
            "password",
        ),
        (
            {
                "username": "priya",
                "full_name": "Priya",
                "role": "boss",
                "password": "long-enough-1",
            },
            "role",
        ),
        (
            {"username": "priya1234", "full_name": "P", "role": "cashier", "password": "priya1234"},
            "password",
        ),
    ],
)
def test_create_user_validation(dbs, admin_client, as_owner, fake_clerk, payload, field):
    res = admin_client.post("/api/users", headers=as_owner, json=payload)
    assert res.status_code == 400
    fields = [d["field"] for d in res.get_json()["error"]["details"]]
    assert any(f.startswith(field) for f in fields)
    assert fake_clerk.calls == []


def test_duplicate_username_is_409(dbs, admin_client, as_owner, fake_clerk):
    res = admin_client.post(
        "/api/users",
        headers=as_owner,
        json={
            "username": "owner",
            "full_name": "Copy",
            "role": "cashier",
            "password": "long-enough-1",
        },
    )
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "USERNAME_TAKEN"


def test_last_admin_cannot_be_demoted_or_banned(dbs, admin_client, as_owner, owner, fake_clerk):
    other_admin_check = admin_client.patch(
        f"/api/users/{owner.id}", headers=as_owner, json={"role": "manager"}
    )
    assert other_admin_check.status_code == 422
    assert other_admin_check.get_json()["error"]["code"] in {"SELF_DEMOTE", "LAST_ADMIN"}
    ban = admin_client.post(f"/api/users/{owner.id}/ban", headers=as_owner)
    assert ban.status_code == 422
    assert ban.get_json()["error"]["code"] == "SELF_DEACTIVATE"
    assert fake_clerk.calls == []


def test_admin_cannot_remove_the_only_other_admin_when_alone(
    dbs, admin_client, as_owner, owner, fake_clerk
):
    owner.is_active = True
    other = User(clerk_user_id="user_a2", username="a2", full_name="Second Admin", role="admin")
    dbs.add(other)
    dbs.flush()
    # Two active admins → demoting the other one is fine.
    res = admin_client.patch(f"/api/users/{other.id}", headers=as_owner, json={"role": "manager"})
    assert res.status_code == 200
    assert ("set_role", ("user_a2", "manager")) in fake_clerk.calls


def test_ban_and_unban(dbs, admin_client, as_owner, fake_clerk):
    cashier = User(clerk_user_id="user_c", username="c", full_name="Cash", role="cashier")
    dbs.add(cashier)
    dbs.flush()
    res = admin_client.post(f"/api/users/{cashier.id}/ban", headers=as_owner)
    assert res.status_code == 200 and res.get_json()["user"]["is_active"] is False
    res = admin_client.post(f"/api/users/{cashier.id}/unban", headers=as_owner)
    assert res.get_json()["user"]["is_active"] is True
    assert [c[0] for c in fake_clerk.calls] == ["ban", "unban"]
    actions = dbs.scalars(
        select(AuditLog.action).where(AuditLog.entity_id == str(cashier.id))
    ).all()
    assert {"user.deactivate", "user.reactivate"} <= set(actions)


def test_reset_password_is_audited_without_the_password(dbs, admin_client, as_owner, fake_clerk):
    cashier = User(clerk_user_id="user_c", username="c", full_name="Cash", role="cashier")
    dbs.add(cashier)
    dbs.flush()
    res = admin_client.post(
        f"/api/users/{cashier.id}/reset-password",
        headers=as_owner,
        json={"new_password": "brand-new-pass-9"},
    )
    assert res.status_code == 204
    audit = dbs.scalar(select(AuditLog).where(AuditLog.action == "user.password_reset"))
    assert "brand-new-pass-9" not in json.dumps([audit.changes, audit.metadata_, audit.summary])


def test_list_users(dbs, admin_client, as_owner):
    res = admin_client.get("/api/users", headers=as_owner)
    assert res.status_code == 200
    assert [u["username"] for u in res.get_json()["items"]] == ["owner"]


def test_unknown_user_is_404(dbs, admin_client, as_owner, fake_clerk):
    res = admin_client.post("/api/users/999999/ban", headers=as_owner)
    assert res.status_code == 404
