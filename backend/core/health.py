"""GET /api/health — public, cheap; also used by the POS to pre-warm its serverless function."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify
from flask.typing import ResponseReturnValue
from sqlalchemy import text

from core import __version__
from core.db import db

log = logging.getLogger(__name__)


def make_health_blueprint(server: str) -> Blueprint:
    bp = Blueprint("health", __name__)

    @bp.get("/api/health")
    def health() -> ResponseReturnValue:
        try:
            db.session.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception:
            log.exception("Health check: database unreachable")
            db.session.rollback()
            db_status = "error"
        body = {"status": "ok", "server": server, "db": db_status, "version": __version__}
        return jsonify(body), (200 if db_status == "ok" else 503)

    return bp
