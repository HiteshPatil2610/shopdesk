"""SERVER 2 — Billing Counter API. Product lookup, cart quote, confirm/reject orders.

Never registers admin routes and never returns cost price or profit (BR-12).
"""

from __future__ import annotations

from flask import Flask

from core.app_factory import build_base_app
from core.config import Settings


def create_app(settings: Settings | None = None) -> Flask:
    return build_base_app("pos", settings)
