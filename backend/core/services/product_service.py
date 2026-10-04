"""Products and categories (spec 03). Every write: one transaction + audit row (BR-8)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from core.actor import ActorContext
from core.db import db, transaction
from core.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from core.media import delete_image_quietly, upload_product_image
from core.models import Category, Product
from core.money import money_str
from core.pricing import calculate, selling_price_for
from core.schemas.products import CategoryCreate, ProductCreate, ProductListQuery, ProductUpdate
from core.services import audit_service, pricing_service, stock_service

AUDITED_FIELDS = (
    "name",
    "category_id",
    "unit",
    "barcode",
    "description",
    "reorder_level",
    "cost_price",
    "market_price",
    "selling_price",
    "mp_is_manual",
    "sp_is_manual",
    "mp_round_mode",
)


# --- categories ------------------------------------------------------------------------


def list_categories() -> list[Category]:
    return list(db.session.scalars(select(Category).order_by(Category.name)).all())


def create_category(data: CategoryCreate, actor: ActorContext) -> Category:
    exists = db.session.scalar(
        select(Category.id).where(func.lower(Category.name) == data.name.lower())
    )
    if exists:
        raise ConflictError("A category with that name already exists", code="CATEGORY_EXISTS")
    with transaction():
        category = Category(name=data.name)
        db.session.add(category)
        db.session.flush()
        audit_service.record(
            actor, "category.create", "category", category.id, f"Category '{category.name}' created"
        )
    return category


def _check_category(category_id: int | None) -> None:
    if category_id is not None and db.session.get(Category, category_id) is None:
        raise ValidationError("Unknown category", code="CATEGORY_NOT_FOUND")


# --- reading ---------------------------------------------------------------------------


def get(product_id: int) -> Product:
    product: Product | None = db.session.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
    return product


def list_products(
    query: ProductListQuery, *, active_only: bool = False
) -> tuple[list[Product], int]:
    stmt = select(Product)
    if active_only or not query.include_inactive:
        stmt = stmt.where(Product.is_active)
    if query.search:
        term = f"%{query.search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Product.name).like(term),
                func.lower(Product.code).like(term),
                Product.barcode == query.search,
            )
        )
    if query.category_id:
        stmt = stmt.where(Product.category_id == query.category_id)
    if query.low_stock:
        stmt = stmt.where(Product.quantity <= Product.reorder_level)

    total = int(db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    order = {
        "name": func.lower(Product.name),
        "-name": func.lower(Product.name).desc(),
        "code": Product.code,
        "-updated_at": Product.updated_at.desc(),
        "quantity": Product.quantity,
        "-quantity": Product.quantity.desc(),
        "market_price": Product.market_price,
    }[query.sort]
    rows = db.session.scalars(
        stmt.order_by(order, Product.id)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    return list(rows), total


def lookup(code_or_barcode: str) -> Product:
    """POS: match code (case-insensitive) or barcode, active products only."""
    term = code_or_barcode.strip()
    product: Product | None = db.session.scalar(
        select(Product).where(
            Product.is_active,
            or_(func.upper(Product.code) == term.upper(), Product.barcode == term),
        )
    )
    if product is None:
        raise NotFoundError(f"No product with code {term}", code="PRODUCT_NOT_FOUND")
    return product


# --- writing ---------------------------------------------------------------------------


def _snapshot(product: Product) -> dict[str, Any]:
    return {name: getattr(product, name) for name in AUDITED_FIELDS}


def _check_price_order(cost: Decimal, sp: Decimal, mp: Decimal) -> None:
    """BR-2: cost ≤ SP ≤ MP, with a message that says exactly what to fix."""
    if sp < cost:
        raise BusinessRuleError(
            f"Selling price ₹{money_str(sp)} is below cost ₹{money_str(cost)}. Raise the SP or set it to auto.",
            code="PRICE_RULE_VIOLATION",
        )
    if sp > mp:
        raise BusinessRuleError(
            f"Selling price ₹{money_str(sp)} is above market price ₹{money_str(mp)}.",
            code="PRICE_RULE_VIOLATION",
        )


def _next_code() -> str:
    number = db.session.scalar(text("SELECT nextval('product_code_seq')"))
    return f"P{int(number):05d}"


def _barcode_taken(barcode: str, exclude_id: int | None = None) -> bool:
    stmt = select(Product.id).where(Product.barcode == barcode)
    if exclude_id:
        stmt = stmt.where(Product.id != exclude_id)
    return db.session.scalar(stmt) is not None


def create(data: ProductCreate, image: bytes | None, actor: ActorContext) -> Product:
    _check_category(data.category_id)
    if data.barcode and _barcode_taken(data.barcode):
        raise ConflictError("That barcode is already used by another product", code="BARCODE_TAKEN")

    rules = pricing_service.get_rules()
    auto = calculate(data.cost_price, rules, mp_mode=data.mp_round_mode)
    mp = data.market_price if data.market_price is not None else auto.market_price
    if data.selling_price is not None:
        sp = data.selling_price
    elif data.market_price is not None:
        sp = selling_price_for(mp, data.cost_price, rules)
    else:
        sp = auto.selling_price
    _check_price_order(data.cost_price, sp, mp)

    public_id = upload_product_image(image) if image else None
    try:
        with transaction():
            product = Product(
                code=_next_code(),
                barcode=data.barcode,
                name=data.name,
                description=data.description,
                category_id=data.category_id,
                unit=data.unit,
                image_public_id=public_id,
                cost_price=data.cost_price,
                market_price=mp,
                selling_price=sp,
                mp_is_manual=data.market_price is not None,
                sp_is_manual=data.selling_price is not None,
                mp_round_mode=data.mp_round_mode,
                quantity=data.quantity,
                reorder_level=data.reorder_level,
                created_by=actor.user_id,
                updated_by=actor.user_id,
            )
            db.session.add(product)
            db.session.flush()
            stock_service.record_initial(product, actor)
            audit_service.record(
                actor,
                "product.create",
                "product",
                product.id,
                f"{product.code} {product.name} created: cost {money_str(product.cost_price)}, "
                f"MP {money_str(mp)}, SP {money_str(sp)}, qty {data.quantity}",
                changes={k: [None, v] for k, v in _snapshot(product).items() if v is not None},
                metadata={"quantity": data.quantity, "image": bool(public_id)},
            )
    except Exception:
        delete_image_quietly(public_id)  # compensating action: don't orphan the upload
        raise
    return product


def update(product_id: int, data: ProductUpdate, actor: ActorContext) -> Product:
    if data.quantity is not None:
        raise ValidationError(
            "Quantity can't be edited here. Use a stock adjustment so the change is recorded.",
            code="USE_STOCK_ADJUSTMENT",
        )
    product = get(product_id)
    if product.version != data.version:
        raise ConflictError(
            "This product was changed by someone else. Reload to see the latest version.",
            code="VERSION_CONFLICT",
            details={
                "current_version": product.version,
                "updated_by": product.updater.display_name if product.updater else None,
                "updated_at": product.updated_at.isoformat() if product.updated_at else None,
            },
        )

    before = _snapshot(product)
    try:
        return _apply_update(product, data, before, actor)
    except Exception:
        # Never leave a half-edited product in the session (it would be autoflushed later).
        db.session.rollback()
        raise


def _apply_update(
    product: Product, data: ProductUpdate, before: dict[str, Any], actor: ActorContext
) -> Product:
    fields = data.model_dump(
        exclude_unset=True, exclude={"version", "quantity", "clear_category", "clear_barcode"}
    )

    if data.clear_category:
        product.category_id = None
    elif "category_id" in fields and fields["category_id"] is not None:
        _check_category(fields["category_id"])
        product.category_id = fields["category_id"]
    if data.clear_barcode:
        product.barcode = None
    elif fields.get("barcode"):
        if _barcode_taken(fields["barcode"], exclude_id=product.id):
            raise ConflictError(
                "That barcode is already used by another product", code="BARCODE_TAKEN"
            )
        product.barcode = fields["barcode"]
    for name in ("name", "unit", "description", "reorder_level"):
        if name in fields and fields[name] is not None:
            setattr(product, name, fields[name])
    if "description" in fields and fields["description"] is None:
        product.description = None

    _apply_price_changes(product, fields)

    changes = audit_service.diff(before, _snapshot(product))
    if not changes:
        db.session.rollback()
        return product
    try:
        with transaction():
            product.updated_by = actor.user_id
            db.session.flush()
            price_keys = {"cost_price", "market_price", "selling_price"}
            summary = ", ".join(
                f"{k} {v[0]} → {v[1]}" if k in price_keys else k for k, v in changes.items()
            )
            audit_service.record(
                actor,
                "product.update",
                "product",
                product.id,
                f"{product.code} {product.name}: {summary}",
                changes=changes,
            )
    except StaleDataError as exc:
        raise ConflictError(
            "This product was changed by someone else. Reload to see the latest version.",
            code="VERSION_CONFLICT",
        ) from exc
    except IntegrityError as exc:
        raise ConflictError("That change conflicts with another product", code="CONFLICT") from exc
    return product


def _apply_price_changes(product: Product, fields: dict[str, Any]) -> None:
    """Recalculation rules (spec 03 §6 PATCH): manual prices are kept, auto ones follow cost/MP."""
    rules = pricing_service.get_rules()
    if "mp_round_mode" in fields and fields["mp_round_mode"]:
        product.mp_round_mode = fields["mp_round_mode"]
    if fields.get("cost_price") is not None:
        product.cost_price = fields["cost_price"]

    # Manual flags: explicit values win; typing a price marks it manual.
    if fields.get("market_price") is not None:
        product.market_price, product.mp_is_manual = fields["market_price"], True
    elif fields.get("mp_is_manual") is False:
        product.mp_is_manual = False
    if fields.get("selling_price") is not None:
        product.selling_price, product.sp_is_manual = fields["selling_price"], True
    elif fields.get("sp_is_manual") is False:
        product.sp_is_manual = False

    cost = Decimal(product.cost_price)
    if not product.mp_is_manual:
        product.market_price = calculate(cost, rules, mp_mode=product.mp_round_mode).market_price  # type: ignore[arg-type]
    if not product.sp_is_manual:
        product.selling_price = selling_price_for(Decimal(product.market_price), cost, rules)
    _check_price_order(cost, Decimal(product.selling_price), Decimal(product.market_price))


def recalculate(product_id: int, reset_manual: bool, version: int, actor: ActorContext) -> Product:
    """Re-apply the current pricing rules. Updates always recompute non-manual prices, so this
    is an update with no field changes (optionally switching both prices back to auto)."""
    flags: dict[str, Any] = {"mp_is_manual": False, "sp_is_manual": False} if reset_manual else {}
    return update(product_id, ProductUpdate(version=version, **flags), actor)


def set_active(product_id: int, active: bool, actor: ActorContext) -> Product:
    """BR-10: soft delete only — products referenced by orders are never hard-deleted."""
    product = get(product_id)
    if product.is_active == active:
        return product
    with transaction():
        product.is_active = active
        product.updated_by = actor.user_id
        audit_service.record(
            actor,
            "product.activate" if active else "product.deactivate",
            "product",
            product.id,
            f"{product.code} {product.name} {'reactivated' if active else 'deactivated'}",
            changes={"is_active": [not active, active]},
        )
    return product


def replace_image(product_id: int, image: bytes | None, actor: ActorContext) -> Product:
    """Upload first, swap in one transaction, delete the old asset only after commit."""
    product = get(product_id)
    old = product.image_public_id
    new = upload_product_image(image) if image else None
    try:
        with transaction():
            product.image_public_id = new
            product.updated_by = actor.user_id
            audit_service.record(
                actor,
                "product.image_update",
                "product",
                product.id,
                f"{product.code} {product.name}: image {'replaced' if new else 'removed'}",
                changes={"image_public_id": [old, new]},
            )
    except Exception:
        delete_image_quietly(new)
        raise
    delete_image_quietly(old)
    return product
