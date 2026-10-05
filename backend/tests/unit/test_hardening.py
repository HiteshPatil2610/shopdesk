import io

import pytest
from flask import Flask, request

from core.errors import register_error_handlers
from core.hardening import install_body_limits, install_headers, install_rate_limits


def test_headers(client):
    response = client.get("/api/missing")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert client.application.config["MAX_CONTENT_LENGTH"] == 4 * 1024 * 1024


def test_shared_area_buckets_and_retry_after(settings, make_token):
    app = Flask("limits-test")
    app.config["SHOPDESK_SETTINGS"] = settings.model_copy(update={"app_env": "development"})
    register_error_handlers(app)
    install_headers(app)
    paths = [
        "/api/admin/write-a",
        "/api/admin/write-b",
        "/api/pos/write",
        "/api/pos/cart/quote",
        "/api/admin/export.csv",
        "/api/admin/other.csv",
        "/api/webhooks/clerk",
        "/api/health",
        "/api/auth/me",
    ]
    for path in paths:
        app.add_url_rule(
            path, endpoint=path, view_func=lambda: {"ok": True}, methods=["GET", "POST"]
        )
    install_rate_limits(app)
    client = app.test_client()
    for index in range(120):
        assert (
            client.post("/api/admin/write-a" if index % 2 else "/api/admin/write-b").status_code
            == 200
        )
    blocked = client.post("/api/admin/write-b", headers={"X-Forwarded-For": "different-ip"})
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
    assert blocked.get_json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert client.get("/api/health").status_code == 200
    # Admin exhaustion cannot consume POS write, quote or export budgets.
    for _ in range(120):
        assert client.post("/api/pos/write").status_code == 200
    assert client.post("/api/pos/write").status_code == 429
    for index in range(5):
        assert (
            client.get("/api/admin/export.csv" if index % 2 else "/api/admin/other.csv").status_code
            == 200
        )
    assert client.get("/api/admin/export.csv").status_code == 429
    for _ in range(300):
        assert client.post("/api/pos/cart/quote").status_code == 200
    assert client.post("/api/pos/cart/quote").status_code == 429
    for _ in range(60):
        assert client.post("/api/webhooks/clerk").status_code == 200
        assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/webhooks/clerk").status_code == 429
    assert client.get("/api/auth/me").status_code == 429
    token = make_token(sub="other_user")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/admin/write-a", headers=headers).status_code == 200
    for _ in range(65):
        assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert (
        client.post("/api/admin/write-a", headers={"Authorization": "Bearer forged"}).status_code
        == 429
    )


@pytest.mark.parametrize(
    "path", ["/api/pos/cart/quote", "/api/admin/products", "/api/webhooks/clerk"]
)
@pytest.mark.parametrize("streamed", [False, True])
def test_small_body_cap(settings, path, streamed):
    app = Flask("body-limit")
    app.config.update(MAX_CONTENT_LENGTH=4 * 1024 * 1024, SHOPDESK_SETTINGS=settings)
    register_error_handlers(app)
    app.add_url_rule(path, view_func=lambda: {"length": len(request.get_data())}, methods=["POST"])
    install_body_limits(app)
    data = b"x" * (300 * 1024)
    kwargs = (
        {
            "environ_overrides": {"CONTENT_LENGTH": None, "wsgi.input_terminated": True},
            "input_stream": io.BytesIO(data),
        }
        if streamed
        else {"data": data}
    )
    assert app.test_client().post(path, **kwargs).status_code == 413


def test_only_image_routes_accept_large_multipart(settings):
    app = Flask("upload-limit")
    app.config.update(MAX_CONTENT_LENGTH=4 * 1024 * 1024, SHOPDESK_SETTINGS=settings)
    register_error_handlers(app)
    for path, endpoint in [
        ("/api/admin/products/1/image", "products.replace_image"),
        ("/api/admin/products", "products.create_product"),
        ("/api/admin/categories", "categories.create"),
    ]:
        app.add_url_rule(
            path,
            endpoint=endpoint,
            view_func=lambda: {"size": len(request.files["image"].read())},
            methods=["POST"],
        )
    install_body_limits(app)
    client = app.test_client()
    for path in ("/api/admin/products/1/image", "/api/admin/products"):
        assert (
            client.post(
                path, data={"image": (io.BytesIO(b"x" * (3 * 1024 * 1024)), "photo.png")}
            ).status_code
            == 200
        )
        assert client.post(path, data={"padding": "x" * (300 * 1024)}).status_code == 413
        assert (
            client.post(
                path, data={"image": (io.BytesIO(b"x" * (4 * 1024 * 1024)), "photo.png")}
            ).status_code
            == 413
        )
    assert (
        client.post(
            "/api/admin/categories", data={"image": (io.BytesIO(b"x" * (300 * 1024)), "photo.png")}
        ).status_code
        == 413
    )
