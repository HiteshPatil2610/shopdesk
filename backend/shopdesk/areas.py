"""Explicit security boundary for each area of the single app."""

from typing import Literal

from flask import Blueprint, current_app, request

Area = Literal["admin", "pos"]
AREA_ROLES: dict[Area, frozenset[str]] = {
    "admin": frozenset({"admin", "manager"}),
    "pos": frozenset({"admin", "manager", "cashier"}),
}


class AreaBlueprint(Blueprint):
    shopdesk_area: Area


def area_blueprint(area: Area, name: str, prefix: str) -> AreaBlueprint:
    bp = AreaBlueprint(name, __name__, url_prefix=f"/api/{area}{prefix}")
    bp.shopdesk_area = area
    return bp


def request_area() -> Area | None:
    bp = current_app.blueprints.get(request.blueprint or "")
    return bp.shopdesk_area if isinstance(bp, AreaBlueprint) else None
