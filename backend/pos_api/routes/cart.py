"""Read-only cart quotes for authenticated staff."""

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue

from core.schemas.orders import QuoteRequest
from core.security import require_role
from core.services import order_service

bp = Blueprint("pos_cart", __name__, url_prefix="/api/cart")


@bp.post("/quote")
@require_role("admin", "manager", "cashier")
def quote() -> ResponseReturnValue:
    data = QuoteRequest.model_validate(request.get_json())
    result = order_service.quote(data.items, data.discount_applied)
    return jsonify(result.model_dump(mode="json"))
