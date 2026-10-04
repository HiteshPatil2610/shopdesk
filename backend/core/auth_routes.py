"""GET /api/auth/me — mounted on both servers. Sign-in/out/refresh are handled by Clerk."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from flask.typing import ResponseReturnValue

from core.db import db
from core.models import User
from core.security import ALL_ROLES, current_actor, require_role


def make_auth_blueprint() -> Blueprint:
    bp = Blueprint("auth", __name__, url_prefix="/api/auth")

    @bp.get("/me")
    @require_role(*ALL_ROLES)  # narrowed per server by SERVER_ROLES
    def me() -> ResponseReturnValue:
        actor = current_actor()
        user = db.session.get(User, actor.user_id)
        assert user is not None  # noqa: S101 - authenticate() just loaded/created it
        return jsonify({"user": user.to_public(), "server": current_app.config["SHOPDESK_SERVER"]})

    return bp
