from flask import Flask, request

from core.errors import register_error_handlers
from core.hardening import install_headers, install_rate_limits


def test_headers_and_body_limits(admin_client, pos_client):
    for client, limit in [(admin_client, 4 * 1024 * 1024), (pos_client, 256 * 1024)]:
        response = client.get("/api/missing")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Cache-Control"] == "no-store"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert client.application.config["MAX_CONTENT_LENGTH"] == limit


def test_shared_buckets_and_retry_after(settings, make_token):
    app = Flask("limits-test")
    app.config.update(
        SHOPDESK_SETTINGS=settings.model_copy(update={"app_env": "development"}),
        SHOPDESK_SERVER="pos",
    )
    register_error_handlers(app)
    install_headers(app)
    paths = [
        "/api/write-a",
        "/api/write-b",
        "/api/cart/quote",
        "/api/export.csv",
        "/api/other.csv",
        "/api/webhooks/clerk",
        "/api/health",
    ]
    for path in paths:
        app.add_url_rule(
            path, endpoint=path, view_func=lambda: {"ok": True}, methods=["GET", "POST"]
        )
    install_rate_limits(app)
    client = app.test_client()
    for index in range(120):
        assert client.post("/api/write-a" if index % 2 else "/api/write-b").status_code == 200
    blocked = client.post("/api/write-b", headers={"X-Forwarded-For": "different-ip"})
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
    assert blocked.get_json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert client.get("/api/health").status_code == 200
    for index in range(5):
        assert client.get("/api/export.csv" if index % 2 else "/api/other.csv").status_code == 200
    assert client.get("/api/export.csv").status_code == 429
    for _ in range(300):
        assert client.post("/api/cart/quote").status_code == 200
    assert client.post("/api/cart/quote").status_code == 429
    for _ in range(60):
        assert client.post("/api/webhooks/clerk").status_code == 200
    assert client.post("/api/webhooks/clerk").status_code == 429
    token = make_token(sub="other_user", azp="http://pos.test")
    assert (
        client.post("/api/write-a", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    )
    assert (
        client.post("/api/write-a", headers={"Authorization": "Bearer forged"}).status_code == 429
    )


def test_body_cap_is_enforced_before_parsing():
    app = Flask("body-limit")
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024
    register_error_handlers(app)

    @app.post("/body")
    def body():
        return {"length": len(request.get_data())}

    assert app.test_client().post("/body", data=b"x" * (256 * 1024 + 1)).status_code == 413
