"""Single ShopDesk API, with independently guarded admin and POS areas."""

from flask import Flask
from flask_migrate import Migrate

from core.config import Settings

migrate = Migrate()


def create_app(settings: Settings | None = None) -> Flask:
    from core import models  # noqa: F401
    from core.app_factory import build_base_app
    from core.auth_routes import make_auth_blueprint
    from core.db import db
    from core.hardening import install_body_limits, install_rate_limits

    app = build_base_app(settings)
    migrate.init_app(app, db, directory="migrations")
    from admin_area.cli import register_cli
    from admin_area.routes import audit, orders, pricing, products, reports, users, webhooks
    from pos_area.routes import cart
    from pos_area.routes import orders as pos_orders
    from pos_area.routes import products as pos_products

    for bp in (
        make_auth_blueprint(),
        webhooks.bp,
        users.bp,
        products.bp,
        pricing.bp,
        audit.bp,
        orders.bp,
        reports.bp,
        pos_products.bp,
        cart.bp,
        pos_orders.bp,
    ):
        app.register_blueprint(bp)
    register_cli(app)
    install_body_limits(app)
    install_rate_limits(app)
    return app
