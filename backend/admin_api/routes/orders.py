"""Orders (read-only) and stock adjustments for the Admin Console (spec 07 §6)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue

from core.schemas.audit import AuditQuery
from core.schemas.orders import OrderListQuery, StockAdjustRequest
from core.security import current_actor, require_role
from core.serializers import admin_order_out, movement_out, page_out, product_out
from core.services import audit_view_service, order_service, stock_service

bp = Blueprint("orders", __name__, url_prefix="/api")

STAFF = ("admin", "manager")


@bp.get("/orders")
@require_role(*STAFF)
def list_orders() -> ResponseReturnValue:
    query = OrderListQuery.model_validate(request.args.to_dict())
    rows, total = order_service.list_orders(query)
    return jsonify(page_out([admin_order_out(o) for o in rows], query.page, query.page_size, total))


@bp.get("/orders/<int:order_id>")
@require_role(*STAFF)
def get_order(order_id: int) -> ResponseReturnValue:
    return jsonify({"order": admin_order_out(order_service.get(order_id), with_lines=True)})


@bp.get("/orders/<int:order_id>/audit")
@require_role(*STAFF)
def order_audit(order_id: int) -> ResponseReturnValue:
    order_service.get(order_id)
    filters = {**request.args.to_dict(), "entity_type": "order", "entity_id": str(order_id)}
    return jsonify(audit_view_service.list_rows(AuditQuery.model_validate(filters)))


@bp.post("/stock/<int:product_id>/adjust")
@require_role(*STAFF)
def adjust_stock(product_id: int) -> ResponseReturnValue:
    data = StockAdjustRequest.model_validate(request.get_json(silent=True) or {})
    product = stock_service.adjust(product_id, data.type, data.qty, data.note, current_actor())
    return jsonify({"product": product_out(product)})


@bp.get("/stock/<int:product_id>/movements")
@require_role(*STAFF)
def stock_movements(product_id: int) -> ResponseReturnValue:
    page = max(1, request.args.get("page", 1, type=int) or 1)
    page_size = min(100, max(1, request.args.get("page_size", 25, type=int) or 25))
    rows, total = stock_service.movements(product_id, page, page_size)
    return jsonify(page_out([movement_out(m) for m in rows], page, page_size, total))


@bp.get("/stock/verify")
@require_role("admin")
def verify_stock() -> ResponseReturnValue:
    mismatches = stock_service.verify()
    return jsonify({"ok": not mismatches, "mismatches": mismatches})
