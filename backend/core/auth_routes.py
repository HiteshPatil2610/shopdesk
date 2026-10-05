"""GET /api/auth/me — shared staff identity for both areas. Sign-in/out/refresh are handled by Clerk."""

from __future__ import annotations

from flask import Blueprint, jsonify
from flask.typing import ResponseReturnValue

from core.db import db
from core.models import User
from core.security import ALL_ROLES, current_actor, require_role
from shopdesk.areas import AREA_ROLES


def make_auth_blueprint() -> Blueprint:
    bp = Blueprint("auth", __name__, url_prefix="/api/auth")

    @bp.get("/me")
    @require_role(*ALL_ROLES)  # the only guarded endpoint intentionally shared across areas
    def me() -> ResponseReturnValue:
        actor = current_actor()
        user = db.session.get(User, actor.user_id)
        assert user is not None  # noqa: S101 - authenticate() just loaded/created it
        return jsonify(
            {
                "user": user.to_public(),
                "areas": [area for area, roles in AREA_ROLES.items() if actor.role in roles],
            }
        )

    return bp
