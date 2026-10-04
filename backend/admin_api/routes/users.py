"""Staff accounts (admin only) — spec 02 §8."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue

from core.schemas.users import PasswordReset, UserCreate, UserUpdate
from core.security import current_actor, require_role
from core.services import user_service

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("")
@require_role("admin")
def list_users() -> ResponseReturnValue:
    return jsonify({"items": [u.to_public() for u in user_service.list_users()]})


@bp.post("")
@require_role("admin")
def create_user() -> ResponseReturnValue:
    data = UserCreate.model_validate(request.get_json(silent=True) or {})
    user = user_service.create_user(data, current_actor())
    return jsonify({"user": user.to_public()}), 201


@bp.patch("/<int:user_id>")
@require_role("admin")
def update_user(user_id: int) -> ResponseReturnValue:
    data = UserUpdate.model_validate(request.get_json(silent=True) or {})
    user = user_service.update_user(user_id, data, current_actor())
    return jsonify({"user": user.to_public()})


@bp.post("/<int:user_id>/reset-password")
@require_role("admin")
def reset_password(user_id: int) -> ResponseReturnValue:
    data = PasswordReset.model_validate(request.get_json(silent=True) or {})
    user_service.reset_password(user_id, data, current_actor())
    return "", 204


@bp.post("/<int:user_id>/ban")
@require_role("admin")
def ban(user_id: int) -> ResponseReturnValue:
    user = user_service.set_active(user_id, False, current_actor())
    return jsonify({"user": user.to_public()})


@bp.post("/<int:user_id>/unban")
@require_role("admin")
def unban(user_id: int) -> ResponseReturnValue:
    user = user_service.set_active(user_id, True, current_actor())
    return jsonify({"user": user.to_public()})
