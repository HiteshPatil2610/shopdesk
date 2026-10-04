"""Read-only product list + lookup for the Billing Counter (spec 03 §6). Never returns cost."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue

from core.errors import ValidationError
from core.schemas.products import ProductListQuery
from core.security import require_role
from core.serializers import page_out, pos_product_out
from core.services import product_service

bp = Blueprint("pos_products", __name__, url_prefix="/api/products")

ANY_STAFF = ("admin", "manager", "cashier")


@bp.get("")
@require_role(*ANY_STAFF)
def list_products() -> ResponseReturnValue:
    args = {
        k: v
        for k, v in request.args.to_dict().items()
        if k in {"search", "page", "page_size", "category_id"}
    }
    query = ProductListQuery.model_validate(args)
    rows, total = product_service.list_products(query, active_only=True)
    return jsonify(page_out([pos_product_out(p) for p in rows], query.page, query.page_size, total))


@bp.get("/lookup")
@require_role(*ANY_STAFF)
def lookup() -> ResponseReturnValue:
    code = (request.args.get("code") or "").strip()
    if not code or len(code) > 64:
        raise ValidationError("Enter a product code or barcode", code="CODE_REQUIRED")
    return jsonify({"product": pos_product_out(product_service.lookup(code))})
