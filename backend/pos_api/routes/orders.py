"""Confirm / reject a bill, receipts and the cashier's own orders (spec 07 §6). No cost fields."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from core.config import Settings
from core.schemas.orders import ConfirmRequest, RejectRequest
from core.security import current_actor, require_role
from core.serializers import pos_order_out, receipt_out
from core.services import order_service

bp = Blueprint("pos_orders", __name__, url_prefix="/api/orders")

ANY_STAFF = ("admin", "manager", "cashier")


@bp.post("/confirm")
@require_role(*ANY_STAFF)
def confirm() -> ResponseReturnValue:
    data = ConfirmRequest.model_validate(request.get_json(silent=True) or {})
    order, created = order_service.confirm(data, current_actor())
    return jsonify({"order": pos_order_out(order)}), (201 if created else 200)


@bp.post("/reject")
@require_role(*ANY_STAFF)
def reject() -> ResponseReturnValue:
    data = RejectRequest.model_validate(request.get_json(silent=True) or {})
    order, created = order_service.reject(data, current_actor())
    return jsonify({"order": pos_order_out(order)}), (201 if created else 200)


@bp.get("/<order_number>/receipt")
@require_role(*ANY_STAFF)
def receipt(order_number: str) -> ResponseReturnValue:
    settings: Settings = current_app.config["SHOPDESK_SETTINGS"]
    order = order_service.receipt_order(order_number, current_actor())
    shop = {
        "name": settings.shop_name,
        "address": settings.shop_address,
        "phone": settings.shop_phone,
        "gstin": settings.shop_gstin,
        "footer": settings.receipt_footer,
    }
    return jsonify(receipt_out(order, shop))


@bp.get("/mine")
@require_role(*ANY_STAFF)
def mine() -> ResponseReturnValue:
    orders = order_service.my_orders_today(current_actor())
    return jsonify(
        {
            "items": [
                {
                    "order_number": o.order_number,
                    "status": o.status,
                    "customer_name": o.customer_name,
                    "created_at": o.created_at.isoformat(),
                    "total": pos_order_out(o)["total"],
                }
                for o in orders
            ]
        }
    )
