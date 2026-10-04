"""SERVER 1 — Admin Console API. Products, pricing, stock, users, audit, reports."""

from __future__ import annotations

from flask import Flask
from flask_migrate import Migrate

from core.app_factory import build_base_app
from core.config import Settings
from core.db import db

migrate = Migrate()


def create_app(settings: Settings | None = None) -> Flask:
    app = build_base_app("admin", settings)
    # Only the admin server owns migrations (architecture §2).
    migrate.init_app(app, db, directory="migrations")
    return app
