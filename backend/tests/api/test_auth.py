import pytest
from sqlalchemy import func, select

from core.models import AuditLog, User
from tests.conftest import ADMIN_ORIGIN, POS_ORIGIN

pytestmark = pytest.mark.db


def audit_count(dbs, action: str) -> int:
    return dbs.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == action))


def test_first_sign_in_creates_mirror_user(dbs, client, auth_header):
    res = client.get(
        "/api/auth/me", headers=auth_header(sub="user_owner", role="admin", name="Owner Patil")
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["areas"] == ["admin", "pos"]
    assert body["user"]["role"] == "admin"
    assert body["user"]["full_name"] == "Owner Patil"
    user = dbs.scalar(select(User).where(User.clerk_user_id == "user_owner"))
    assert user is not None and user.last_seen_at is not None
    assert audit_count(dbs, "user.synced") == 1


def test_cashier_can_use_pos(dbs, client, auth_header):
    res = client.get(
        "/api/auth/me", headers=auth_header(sub="user_c", role="cashier", azp=POS_ORIGIN)
    )
    assert res.status_code == 200
    assert res.get_json()["areas"] == ["pos"]


def test_cashier_cannot_use_admin_and_is_audited_once(dbs, client, auth_header):
    headers = auth_header(sub="user_c2", role="cashier", azp=ADMIN_ORIGIN)
    first = client.get("/api/admin/products", headers=headers)
    second = client.get("/api/admin/products", headers=headers)
    assert first.status_code == second.status_code == 403
    assert first.get_json()["error"]["code"] == "ROLE_NOT_ALLOWED"
    assert "Admin Console" in first.get_json()["error"]["message"]
    assert audit_count(dbs, "auth.role_denied") == 1  # throttled


def test_foreign_app_token_is_rejected(dbs, client, auth_header):
    res = client.get("/api/auth/me", headers=auth_header(role="admin", azp="https://other.example"))
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "TOKEN_WRONG_APP"


def test_missing_token_is_401(dbs, client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "AUTH_REQUIRED"


def test_user_without_role_is_refused(dbs, client, auth_header):
    res = client.get("/api/auth/me", headers=auth_header(role=None, azp=POS_ORIGIN))
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "NO_ROLE_ASSIGNED"


def test_deactivated_user_is_cut_off(dbs, client, auth_header):
    dbs.add(User(clerk_user_id="user_gone", full_name="Gone", role="manager", is_active=False))
    dbs.flush()
    res = client.get("/api/auth/me", headers=auth_header(sub="user_gone", role="manager"))
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "ACCOUNT_INACTIVE"


def test_role_change_in_clerk_syncs_mirror(dbs, client, auth_header):
    client.get("/api/auth/me", headers=auth_header(sub="user_m", role="manager"))
    res = client.get("/api/auth/me", headers=auth_header(sub="user_m", role="admin"))
    assert res.get_json()["user"]["role"] == "admin"
    user = dbs.scalar(select(User).where(User.clerk_user_id == "user_m"))
    assert user.role == "admin"
    assert audit_count(dbs, "user.synced") == 2  # created + role change


def test_manager_can_use_admin_but_not_users_page(dbs, client, auth_header):
    headers = auth_header(sub="user_mgr", role="manager")
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    res = client.get("/api/admin/users", headers=headers)
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "ROLE_NOT_ALLOWED"
