import json

import pytest
from sqlalchemy import select

from core.clerk_gateway import ClerkUserInfo
from core.models import AuditLog, User

pytestmark = pytest.mark.db


def test_revoke_sessions_is_audited(dbs, client, as_owner, owner, fake_clerk):
    response = client.post(f"/api/admin/users/{owner.id}/revoke-sessions", headers=as_owner)
    assert response.status_code == 200 and response.get_json()["sessions_revoked"] == 2
    assert ("revoke_sessions", (owner.clerk_user_id,)) in fake_clerk.calls
    row = dbs.scalar(select(AuditLog).where(AuditLog.action == "user.sessions_revoke"))
    assert row.metadata_["sessions_revoked"] == 2


def test_failed_revocation_is_audited(dbs, client, as_owner, owner, fake_clerk, monkeypatch):
    from core.errors import AppError

    def fail(_user_id):
        raise AppError("Clerk unavailable", status=502)

    monkeypatch.setattr(fake_clerk, "revoke_sessions", fail)
    response = client.post(f"/api/admin/users/{owner.id}/revoke-sessions", headers=as_owner)
    assert response.status_code == 502
    assert dbs.scalar(select(AuditLog).where(AuditLog.action == "user.sessions_revoke_failed"))


@pytest.mark.parametrize("role", ["manager", "cashier"])
def test_non_admin_cannot_revoke_sessions(dbs, client, auth_header, fake_clerk, role):
    response = client.post("/api/admin/users/1/revoke-sessions", headers=auth_header(role=role))
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


def test_admin_creates_cashier(dbs, client, as_owner, fake_clerk):
    res = client.post(
        "/api/admin/users",
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
    dbs, client, as_owner, owner
):
    owner.email = "owner@example.test"
    dbs.flush()
    res = client.get("/api/admin/users", headers=as_owner)
    assert res.status_code == 200
    user = res.get_json()["items"][0]
    assert user["username"] == "owner"
    assert user["email"] == "owner@example.test"
    assert user["clerk_user_id"] == "user_owner"
    assert user["created_at"] and user["updated_at"]
    assert not any("password" in key for key in user)


@pytest.mark.parametrize("role", ["manager", "cashier"])
def test_user_details_are_admin_only(dbs, client, as_role, role):
    assert client.get("/api/admin/users", headers=as_role(role)).status_code == 403


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
def test_create_user_validation(dbs, client, as_owner, fake_clerk, payload, field):
    res = client.post("/api/admin/users", headers=as_owner, json=payload)
    assert res.status_code == 400
    fields = [d["field"] for d in res.get_json()["error"]["details"]]
    assert any(f.startswith(field) for f in fields)
    assert fake_clerk.calls == []


def test_duplicate_username_is_409(dbs, client, as_owner, fake_clerk):
    res = client.post(
        "/api/admin/users",
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


def test_last_admin_cannot_be_demoted_or_banned(dbs, client, as_owner, owner, fake_clerk):
    other_admin_check = client.patch(
        f"/api/admin/users/{owner.id}", headers=as_owner, json={"role": "manager"}
    )
    assert other_admin_check.status_code == 422
    assert other_admin_check.get_json()["error"]["code"] in {"SELF_DEMOTE", "LAST_ADMIN"}
    ban = client.post(f"/api/admin/users/{owner.id}/ban", headers=as_owner)
    assert ban.status_code == 422
    assert ban.get_json()["error"]["code"] == "SELF_DEACTIVATE"
    assert fake_clerk.calls == []


def test_admin_cannot_remove_the_only_other_admin_when_alone(
    dbs, client, as_owner, owner, fake_clerk
):
    owner.is_active = True
    other = User(clerk_user_id="user_a2", username="a2", full_name="Second Admin", role="admin")
    dbs.add(other)
    dbs.flush()
    # Two active admins → demoting the other one is fine.
    res = client.patch(f"/api/admin/users/{other.id}", headers=as_owner, json={"role": "manager"})
    assert res.status_code == 200
    assert ("set_role", ("user_a2", "manager")) in fake_clerk.calls


def test_ban_and_unban(dbs, client, as_owner, fake_clerk):
    cashier = User(clerk_user_id="user_c", username="c", full_name="Cash", role="cashier")
    dbs.add(cashier)
    dbs.flush()
    res = client.post(f"/api/admin/users/{cashier.id}/ban", headers=as_owner)
    assert res.status_code == 200 and res.get_json()["user"]["is_active"] is False
    res = client.post(f"/api/admin/users/{cashier.id}/unban", headers=as_owner)
    assert res.get_json()["user"]["is_active"] is True
    assert [c[0] for c in fake_clerk.calls] == ["ban", "unban"]
    actions = dbs.scalars(
        select(AuditLog.action).where(AuditLog.entity_id == str(cashier.id))
    ).all()
    assert {"user.deactivate", "user.reactivate"} <= set(actions)


def test_reset_password_is_audited_without_the_password(dbs, client, as_owner, fake_clerk):
    cashier = User(clerk_user_id="user_c", username="c", full_name="Cash", role="cashier")
    dbs.add(cashier)
    dbs.flush()
    res = client.post(
        f"/api/admin/users/{cashier.id}/reset-password",
        headers=as_owner,
        json={"new_password": "brand-new-pass-9"},
    )
    assert res.status_code == 204
    audit = dbs.scalar(select(AuditLog).where(AuditLog.action == "user.password_reset"))
    assert "brand-new-pass-9" not in json.dumps([audit.changes, audit.metadata_, audit.summary])


def test_list_users(dbs, client, as_owner):
    res = client.get("/api/admin/users", headers=as_owner)
    assert res.status_code == 200
    assert [u["username"] for u in res.get_json()["items"]] == ["owner"]


def test_unknown_user_is_404(dbs, client, as_owner, fake_clerk):
    res = client.post("/api/admin/users/999999/ban", headers=as_owner)
    assert res.status_code == 404


def seed_clerk_owner(fake_clerk):
    fake_clerk.users["user_owner"] = ClerkUserInfo(
        "user_owner", "owner", None, "Owner", "admin", False
    )


def test_directory_refresh_updates_email_and_archives_deleted_users(
    dbs, client, as_owner, fake_clerk
):
    seed_clerk_owner(fake_clerk)
    staff = User(clerk_user_id="user_staff", username="staff", full_name="Staff", role="cashier")
    deleted = User(
        clerk_user_id="user_deleted", username="deleted", full_name="Deleted", role="cashier"
    )
    dbs.add_all([staff, deleted])
    dbs.flush()
    fake_clerk.users["user_staff"] = ClerkUserInfo(
        "user_staff", "staff", "staff@example.com", "Staff Updated", "cashier", False
    )
    response = client.post("/api/admin/users/sync", headers=as_owner)
    assert response.status_code == 200
    items = {u["clerk_user_id"]: u for u in response.get_json()["items"]}
    assert items["user_staff"]["email"] == "staff@example.com"
    assert items["user_staff"]["full_name"] == "Staff Updated"
    assert items["user_deleted"]["is_active"] is False
    assert items["user_deleted"]["deleted_in_clerk"] is True
    assert dbs.get(User, deleted.id) is not None  # Preserve historical FK references.
    response = client.post("/api/admin/users/sync", headers=as_owner)
    assert response.status_code == 200
    assert len(dbs.scalars(select(AuditLog).where(AuditLog.action == "user.deactivate")).all()) == 1


def test_incomplete_directory_does_not_disable_existing_account(
    dbs, client, as_owner, fake_clerk, monkeypatch
):
    seed_clerk_owner(fake_clerk)
    staff = User(clerk_user_id="user_staff", username="staff", full_name="Staff", role="cashier")
    dbs.add(staff)
    dbs.flush()
    fake_clerk.users["user_staff"] = ClerkUserInfo(
        "user_staff", "staff", None, "Staff", "cashier", False
    )
    monkeypatch.setattr(fake_clerk, "list_users", lambda: [fake_clerk.users["user_owner"]])
    assert client.post("/api/admin/users/sync", headers=as_owner).status_code == 200
    assert staff.is_active


def test_clerk_failure_leaves_directory_unchanged(
    dbs, client, as_owner, owner, fake_clerk, monkeypatch
):
    from core.errors import AppError

    def fail():
        raise AppError("Clerk unavailable", status=502)

    monkeypatch.setattr(fake_clerk, "list_users", fail)
    assert client.post("/api/admin/users/sync", headers=as_owner).status_code == 502
    assert owner.is_active


@pytest.mark.parametrize("role", ["manager", "cashier"])
def test_directory_sync_is_admin_only(dbs, client, as_role, fake_clerk, role):
    assert client.post("/api/admin/users/sync", headers=as_role(role)).status_code == 403
    assert not fake_clerk.calls


def test_user_email_create_and_update_are_mirrored(dbs, client, as_owner, fake_clerk):
    response = client.post(
        "/api/admin/users",
        headers=as_owner,
        json={
            "username": "emailstaff",
            "full_name": "Email Staff",
            "role": "cashier",
            "password": "counter-pass-01",
            "email": "staff@example.com",
        },
    )
    assert response.status_code == 201
    user = response.get_json()["user"]
    assert user["email"] == "staff@example.com"
    response = client.patch(
        f"/api/admin/users/{user['id']}", headers=as_owner, json={"email": "updated@example.com"}
    )
    assert response.status_code == 200
    assert response.get_json()["user"]["email"] == "updated@example.com"
    assert ("set_email", ("user_new1", "updated@example.com")) in fake_clerk.calls
    response = client.patch(
        f"/api/admin/users/{user['id']}", headers=as_owner, json={"email": "not-an-email"}
    )
    assert response.status_code == 400
