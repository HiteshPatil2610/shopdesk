"""SERVER 2 — Billing Counter API. Product lookup, cart quote, confirm/reject orders.

Never registers admin routes and never returns cost price or profit (BR-12).
"""

from __future__ import annotations

from flask import Flask

from core import models  # noqa: F401  - registers all tables with the metadata
from core.app_factory import build_base_app
from core.auth_routes import make_auth_blueprint
from core.config import Settings


def create_app(settings: Settings | None = None) -> Flask:
    app = build_base_app("pos", settings)
    from pos_api.routes import cart, products

    app.register_blueprint(make_auth_blueprint())
    app.register_blueprint(products.bp)
    app.register_blueprint(cart.bp)
    return app
