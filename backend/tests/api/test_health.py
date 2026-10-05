import pytest
from sqlalchemy.exc import OperationalError

from core.db import db


@pytest.mark.db
def test_health_reports_db_ok(client, test_db):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok", "app": "shopdesk", "db": "ok", "version": "0.1.0"}


def test_health_returns_503_when_db_down(client, monkeypatch):
    def boom(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("down"))

    monkeypatch.setattr(db.session, "execute", boom)
    res = client.get("/api/health")
    assert res.status_code == 503
    assert res.get_json()["db"] == "error"


def test_request_id_is_echoed_or_generated(client, monkeypatch):
    monkeypatch.setattr(db.session, "execute", lambda *a, **k: None)
    given = client.get("/api/health", headers={"X-Request-ID": "abc12345-req"})
    assert given.headers["X-Request-ID"] == "abc12345-req"
    generated = client.get("/api/health", headers={"X-Request-ID": "bad id!"})
    assert len(generated.headers["X-Request-ID"]) == 32


def test_unknown_route_uses_json_error_shape(client):
    res = client.get("/api/pos/does-not-exist")
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize("origin", ["http://localhost:5173", "https://evil.example", "null"])
@pytest.mark.parametrize(
    "path",
    ["/api/health", "/api/auth/me", "/api/admin/products", "/api/pos/products", "/api/missing"],
)
def test_no_cors_headers(client, monkeypatch, origin, path):
    monkeypatch.setattr(db.session, "execute", lambda *a, **k: None)
    for method in ("GET", "OPTIONS"):
        response = client.open(
            path, method=method, headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
        )
        assert not any(k.lower().startswith("access-control-") for k, _ in response.headers.items())
