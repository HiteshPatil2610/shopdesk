"""SERVER 1 — Admin Console API. Products, pricing, stock, users, audit, reports."""

from __future__ import annotations

from flask import Flask
from flask_migrate import Migrate

from core import models  # noqa: F401  - registers all tables with the metadata
from core.app_factory import build_base_app
from core.auth_routes import make_auth_blueprint
from core.config import Settings
from core.db import db

migrate = Migrate()


def create_app(settings: Settings | None = None) -> Flask:
    app = build_base_app("admin", settings)
    # Only the admin server owns migrations (architecture §2).
    migrate.init_app(app, db, directory="migrations")

    from admin_api.cli import register_cli
    from admin_api.routes import audit, orders, pricing, products, users, webhooks

    app.register_blueprint(make_auth_blueprint())
    app.register_blueprint(users.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(pricing.bp)
    app.register_blueprint(audit.bp)
    app.register_blueprint(orders.bp)
    app.register_blueprint(webhooks.bp)
    register_cli(app)
    return app
