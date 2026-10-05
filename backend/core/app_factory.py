"""Common Flask app setup used by admin_api and pos_api. Each server adds only its own routes."""

from __future__ import annotations

from typing import Literal

from flask import Flask
from flask_cors import CORS

from core.config import Settings, get_settings
from core.db import db, engine_options
from core.errors import register_error_handlers
from core.hardening import install_headers
from core.health import make_health_blueprint
from core.observability import configure_logging, register_request_id

ServerName = Literal["admin", "pos"]


def build_base_app(server: ServerName, settings: Settings | None = None) -> Flask:
    settings = settings or get_settings()
    configure_logging(server, settings.log_level)

    app = Flask(f"shopdesk_{server}")
    app.config.update(
        SQLALCHEMY_DATABASE_URI=settings.effective_database_url,
        SQLALCHEMY_ENGINE_OPTIONS=engine_options(settings),
        # Admin accepts image uploads (under Vercel's ~4.5 MB body cap); POS only small JSON.
        MAX_CONTENT_LENGTH=(
            settings.max_upload_mb * 1024 * 1024 if server == "admin" else 256 * 1024
        ),
        SHOPDESK_SERVER=server,
        SHOPDESK_SETTINGS=settings,
    )
    app.json.sort_keys = False  # type: ignore[attr-defined]  # keep response field order
    if settings.app_env == "test":
        app.config["TESTING"] = True

    db.init_app(app)

    origins = settings.split_csv(
        settings.admin_cors_origins if server == "admin" else settings.pos_cors_origins
    )
    CORS(
        app,
        resources={r"/api/*": {"origins": origins}},
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
        expose_headers=[
            "X-Request-ID",
            "Retry-After",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
        supports_credentials=False,
        max_age=600,
    )

    register_request_id(app)
    install_headers(app)
    if settings.app_env == "production":
        app.config.update(DEBUG=False, PROPAGATE_EXCEPTIONS=False)
    register_error_handlers(app)
    app.register_blueprint(make_health_blueprint(server))
    return app
