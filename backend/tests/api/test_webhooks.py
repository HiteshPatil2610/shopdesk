import json
import time
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from svix.webhooks import Webhook

from core.models import AuditLog, User
from tests.conftest import WEBHOOK_SECRET

pytestmark = pytest.mark.db


def signed(event: dict, msg_id: str = "msg_1", secret: str = WEBHOOK_SECRET) -> tuple[bytes, dict]:
    body = json.dumps(event)
    ts = datetime.fromtimestamp(int(time.time()), tz=UTC)
    signature = Webhook(secret).sign(msg_id, ts, body)
    headers = {
        "svix-id": msg_id,
        "svix-timestamp": str(int(ts.timestamp())),
        "svix-signature": signature,
        "Content-Type": "application/json",
    }
    return body.encode(), headers


def user_event(kind: str = "user.updated", role: str | None = "cashier", **extra) -> dict:
    data = {
        "id": "user_wh",
        "username": "ravi",
        "first_name": "Ravi",
        "last_name": "Kumar",
        "primary_email_address_id": "idn_1",
        "email_addresses": [{"id": "idn_1", "email_address": "ravi@example.com"}],
        "public_metadata": {"role": role} if role else {},
        "banned": False,
    }
    data.update(extra)
    return {"type": kind, "data": data}


def test_user_updated_upserts_mirror(dbs, client):
    body, headers = signed(user_event())
    res = client.post("/api/webhooks/clerk", data=body, headers=headers)
    assert res.status_code == 200
    user = dbs.scalar(select(User).where(User.clerk_user_id == "user_wh"))
    assert (user.username, user.email, user.full_name, user.role) == (
        "ravi",
        "ravi@example.com",
        "Ravi Kumar",
        "cashier",
    )


def test_bad_signature_is_rejected(dbs, client):
    body, headers = signed(user_event(), secret="whsec_" + "A" * 43)
    res = client.post("/api/webhooks/clerk", data=body, headers=headers)
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "BAD_SIGNATURE"


def test_duplicate_delivery_is_processed_once(dbs, client):
    body, headers = signed(user_event(), msg_id="msg_dup")
    assert client.post("/api/webhooks/clerk", data=body, headers=headers).status_code == 200
    second = client.post("/api/webhooks/clerk", data=body, headers=headers)
    assert second.get_json()["status"] == "duplicate"
    synced = dbs.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "user.synced")
    )
    assert synced == 1


def test_user_without_role_is_not_mirrored_yet(dbs, client):
    body, headers = signed(user_event(kind="user.created", role=None), msg_id="msg_norole")
    client.post("/api/webhooks/clerk", data=body, headers=headers)
    assert dbs.scalar(select(User).where(User.clerk_user_id == "user_wh")) is None


def test_user_deleted_deactivates(dbs, client):
    dbs.add(User(clerk_user_id="user_wh", full_name="Ravi", role="cashier"))
    dbs.flush()
    body, headers = signed({"type": "user.deleted", "data": {"id": "user_wh"}}, msg_id="msg_del")
    client.post("/api/webhooks/clerk", data=body, headers=headers)
    assert dbs.scalar(select(User.is_active).where(User.clerk_user_id == "user_wh")) is False


def test_session_events_are_audited(dbs, client):
    dbs.add(User(clerk_user_id="user_wh", username="ravi", full_name="Ravi", role="cashier"))
    dbs.flush()
    for i, kind in enumerate(["session.created", "session.ended"]):
        body, headers = signed(
            {"type": kind, "data": {"id": "sess_1", "user_id": "user_wh"}}, msg_id=f"msg_s{i}"
        )
        client.post("/api/webhooks/clerk", data=body, headers=headers)
    actions = dbs.scalars(select(AuditLog.action).order_by(AuditLog.id)).all()
    assert actions == ["auth.login", "auth.logout"]


def test_webhook_without_secret_configured(dbs, settings):
    from shopdesk import create_app

    app = create_app(settings.model_copy(update={"clerk_webhook_signing_secret": None}))
    res = app.test_client().post("/api/webhooks/clerk", data=b"{}")
    assert res.status_code == 503
