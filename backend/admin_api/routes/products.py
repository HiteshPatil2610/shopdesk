"""Products + categories — Admin Console (spec 03 §6), managers and admins."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue

from core.errors import ValidationError
from core.schemas.products import CategoryCreate, ProductCreate, ProductListQuery, ProductUpdate
from core.security import current_actor, require_role
from core.serializers import category_out, page_out, product_out
from core.services import product_service

bp = Blueprint("products", __name__, url_prefix="/api")

STAFF = ("admin", "manager")


def _image_bytes() -> bytes | None:
    file = request.files.get("image")
    if file is None or not file.filename:
        return None
    return file.read()


@bp.get("/categories")
@require_role(*STAFF)
def list_categories() -> ResponseReturnValue:
    return jsonify({"items": [category_out(c) for c in product_service.list_categories()]})


@bp.post("/categories")
@require_role(*STAFF)
def create_category() -> ResponseReturnValue:
    data = CategoryCreate.model_validate(request.get_json(silent=True) or {})
    return (
        jsonify({"category": category_out(product_service.create_category(data, current_actor()))}),
        201,
    )


@bp.get("/products")
@require_role(*STAFF)
def list_products() -> ResponseReturnValue:
    query = ProductListQuery.model_validate(request.args.to_dict())
    rows, total = product_service.list_products(query)
    return jsonify(page_out([product_out(p) for p in rows], query.page, query.page_size, total))


@bp.post("/products")
@require_role(*STAFF)
def create_product() -> ResponseReturnValue:
    # multipart/form-data (fields + optional "image") or JSON without an image
    payload = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    data = ProductCreate.model_validate(payload)
    product = product_service.create(data, _image_bytes(), current_actor())
    return jsonify({"product": product_out(product)}), 201


@bp.get("/products/<int:product_id>")
@require_role(*STAFF)
def get_product(product_id: int) -> ResponseReturnValue:
    return jsonify({"product": product_out(product_service.get(product_id))})


@bp.patch("/products/<int:product_id>")
@require_role(*STAFF)
def update_product(product_id: int) -> ResponseReturnValue:
    data = ProductUpdate.model_validate(request.get_json(silent=True) or {})
    product = product_service.update(product_id, data, current_actor())
    return jsonify({"product": product_out(product)})


@bp.post("/products/<int:product_id>/image")
@require_role(*STAFF)
def replace_image(product_id: int) -> ResponseReturnValue:
    image = _image_bytes()
    if image is None:
        raise ValidationError("Choose an image to upload", code="IMAGE_REQUIRED")
    return jsonify(
        {"product": product_out(product_service.replace_image(product_id, image, current_actor()))}
    )


@bp.delete("/products/<int:product_id>/image")
@require_role(*STAFF)
def remove_image(product_id: int) -> ResponseReturnValue:
    return jsonify(
        {"product": product_out(product_service.replace_image(product_id, None, current_actor()))}
    )


@bp.post("/products/<int:product_id>/deactivate")
@require_role(*STAFF)
def deactivate(product_id: int) -> ResponseReturnValue:
    return jsonify(
        {"product": product_out(product_service.set_active(product_id, False, current_actor()))}
    )


@bp.post("/products/<int:product_id>/activate")
@require_role(*STAFF)
def activate(product_id: int) -> ResponseReturnValue:
    return jsonify(
        {"product": product_out(product_service.set_active(product_id, True, current_actor()))}
    )


@bp.post("/products/<int:product_id>/recalculate-prices")
@require_role(*STAFF)
def recalculate(product_id: int) -> ResponseReturnValue:
    body = request.get_json(silent=True) or {}
    version = body.get("version")
    if not isinstance(version, int):
        raise ValidationError("version is required", code="VALIDATION_ERROR")
    product = product_service.recalculate(
        product_id, bool(body.get("reset_manual")), version, current_actor()
    )
    return jsonify({"product": product_out(product)})
