"""Base configuration for the single ShopDesk app. Area routes are registered by shopdesk."""

from __future__ import annotations

from flask import Flask

from core.config import Settings, get_settings
from core.db import db, engine_options
from core.errors import register_error_handlers
from core.hardening import install_headers
from core.health import make_health_blueprint
from core.observability import configure_logging, register_request_id


def build_base_app(settings: Settings | None = None) -> Flask:
    settings = settings or get_settings()
    configure_logging("shopdesk", settings.log_level)

    app = Flask("shopdesk")
    app.config.update(
        SQLALCHEMY_DATABASE_URI=settings.effective_database_url,
        SQLALCHEMY_ENGINE_OPTIONS=engine_options(settings),
        MAX_CONTENT_LENGTH=settings.max_upload_mb * 1024 * 1024,
        SHOPDESK_SETTINGS=settings,
    )
    app.json.sort_keys = False  # type: ignore[attr-defined]  # keep response field order
    if settings.app_env == "test":
        app.config["TESTING"] = True

    db.init_app(app)

    register_request_id(app)
    install_headers(app)
    if settings.app_env == "production":
        app.config.update(DEBUG=False, PROPAGATE_EXCEPTIONS=False)
    register_error_handlers(app)
    app.register_blueprint(make_health_blueprint())
    return app
