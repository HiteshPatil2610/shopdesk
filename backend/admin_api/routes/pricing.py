"""Pricing preview + settings (spec 04 §7). Preview for staff; changing rules is admin-only."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue

from core.schemas.products import PricingPreviewIn, PricingSettingsIn
from core.security import current_actor, require_role
from core.services import pricing_service

bp = Blueprint("pricing", __name__, url_prefix="/api/pricing")


@bp.post("/preview")
@require_role("admin", "manager")
def preview() -> ResponseReturnValue:
    data = PricingPreviewIn.model_validate(request.get_json(silent=True) or {})
    rules = pricing_service.rules_from_input(data.settings) if data.settings else None
    return jsonify(
        pricing_service.preview(data.cost_price, data.mp_round_mode, rules, data.market_price)
    )


@bp.get("/settings")
@require_role("admin", "manager")
def get_settings() -> ResponseReturnValue:
    return jsonify({"settings": pricing_service.settings_out(pricing_service.get_rules())})


@bp.put("/settings")
@require_role("admin")
def put_settings() -> ResponseReturnValue:
    data = PricingSettingsIn.model_validate(request.get_json(silent=True) or {})
    rules = pricing_service.update_settings(data, current_actor())
    return jsonify({"settings": pricing_service.settings_out(rules)})


@bp.post("/apply")
@require_role("admin")
def apply() -> ResponseReturnValue:
    dry_run = bool((request.get_json(silent=True) or {}).get("dry_run", True))
    return jsonify(pricing_service.apply_to_products(dry_run, current_actor()))
