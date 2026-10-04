import pytest
from sqlalchemy.exc import OperationalError

from core.db import db


@pytest.mark.db
@pytest.mark.parametrize(
    ("client_fixture", "server"), [("admin_client", "admin"), ("pos_client", "pos")]
)
def test_health_reports_db_ok(request, test_db, client_fixture, server):
    client = request.getfixturevalue(client_fixture)
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok", "server": server, "db": "ok", "version": "0.1.0"}


@pytest.mark.parametrize("client_fixture", ["admin_client", "pos_client"])
def test_health_returns_503_when_db_down(request, monkeypatch, client_fixture):
    client = request.getfixturevalue(client_fixture)

    def boom(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("down"))

    monkeypatch.setattr(db.session, "execute", boom)
    res = client.get("/api/health")
    assert res.status_code == 503
    assert res.get_json()["db"] == "error"


def test_request_id_is_echoed_or_generated(admin_client, monkeypatch):
    monkeypatch.setattr(db.session, "execute", lambda *a, **k: None)
    given = admin_client.get("/api/health", headers={"X-Request-ID": "abc12345-req"})
    assert given.headers["X-Request-ID"] == "abc12345-req"
    generated = admin_client.get("/api/health", headers={"X-Request-ID": "bad id!"})
    assert len(generated.headers["X-Request-ID"]) == 32


def test_unknown_route_uses_json_error_shape(pos_client):
    res = pos_client.get("/api/does-not-exist")
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "NOT_FOUND"


def test_cors_only_allows_own_frontend(admin_client, pos_client, monkeypatch):
    monkeypatch.setattr(db.session, "execute", lambda *a, **k: None)
    admin_origin = {"Origin": "http://localhost:5173"}
    pos_origin = {"Origin": "http://localhost:5174"}
    assert (
        admin_client.get("/api/health", headers=admin_origin).headers.get(
            "Access-Control-Allow-Origin"
        )
        == "http://localhost:5173"
    )
    assert (
        "Access-Control-Allow-Origin"
        not in admin_client.get("/api/health", headers=pos_origin).headers
    )
    assert (
        pos_client.get("/api/health", headers=pos_origin).headers.get("Access-Control-Allow-Origin")
        == "http://localhost:5174"
    )


def test_pos_rejects_large_bodies(pos_client):
    res = pos_client.post("/api/health", data=b"x" * (300 * 1024))
    assert res.status_code in (405, 413)
