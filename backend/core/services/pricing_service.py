"""Pricing settings + applying the formula to products (spec 04)."""

from __future__ import annotations

from dataclasses import asdict, fields
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from core.actor import ActorContext
from core.db import db, transaction
from core.errors import BusinessRuleError
from core.models import PricingSettings, Product
from core.models.base import utcnow
from core.money import money_str
from core.pricing import MpMode, PriceResult, PricingRules, calculate, margin_pct
from core.schemas.products import PricingSettingsIn
from core.services import audit_service

RULE_FIELDS = [f.name for f in fields(PricingRules)]


def _row() -> PricingSettings:
    row = db.session.get(PricingSettings, 1)
    if row is None:  # seeded by migration 0003; recreate defensively
        row = PricingSettings(id=1, **asdict(PricingRules()))
        db.session.add(row)
        db.session.flush()
    return row


def get_rules() -> PricingRules:
    row = _row()
    values: dict[str, Any] = {}
    for name in RULE_FIELDS:
        value = getattr(row, name)
        values[name] = value if isinstance(value, bool) else Decimal(value)
    return PricingRules(**values)


def rules_from_input(data: PricingSettingsIn) -> PricingRules:
    rules = PricingRules(**data.model_dump())
    _validate(rules)
    return rules


def _validate(rules: PricingRules) -> None:
    if rules.small_mp_alt_step < rules.small_mp_step or rules.mp_alt_step < rules.mp_step:
        raise BusinessRuleError(
            "The alternative (bigger) rounding step must be at least the default step",
            code="PRICING_RULE_INVALID",
        )


def settings_out(rules: PricingRules) -> dict[str, str | bool]:
    return {
        name: value if isinstance(value, bool) else money_str(value)
        for name, value in asdict(rules).items()
    }


def update_settings(data: PricingSettingsIn, actor: ActorContext) -> PricingRules:
    """PE-4: changing settings never reprices products by itself."""
    new_rules = rules_from_input(data)
    old_rules = get_rules()
    changes = audit_service.diff(asdict(old_rules), asdict(new_rules))
    if not changes:
        return old_rules
    with transaction():
        row = _row()
        for name, value in asdict(new_rules).items():
            setattr(row, name, value)
        row.updated_by = actor.user_id
        row.updated_at = utcnow()
        audit_service.record(
            actor,
            "pricing_settings.update",
            "pricing_settings",
            1,
            "Pricing rules changed: " + ", ".join(changes),
            changes=changes,
        )
    return new_rules


def preview_out(result: PriceResult, cost: Decimal) -> dict[str, Any]:
    return {
        "cost_price": money_str(cost),
        "raw_market_price": money_str(result.raw_mp),
        "markup_pct": money_str(result.markup_pct),
        "market_price": money_str(result.market_price),
        "selling_price": money_str(result.selling_price),
        "mp_round_mode": result.mp_mode,
        "mp_options": [
            {"mode": o.mode, "value": money_str(o.value), "step": money_str(o.step)}
            for o in result.mp_options
        ],
        "mp_margin_pct": _pct(margin_pct(result.market_price, cost)),
        "sp_margin_pct": _pct(margin_pct(result.selling_price, cost)),
        "explanation": result.explanation,
    }


def _pct(value: Decimal | None) -> str | None:
    return money_str(value) if value is not None else None


def preview(
    cost: Decimal,
    mode: MpMode,
    rules: PricingRules | None = None,
    market_price: Decimal | None = None,
) -> dict[str, Any]:
    rules = rules or get_rules()
    result = calculate(cost, rules, mp_mode=mode)
    out = preview_out(result, cost)
    if market_price is not None:
        from core.pricing import selling_price_for

        sp = selling_price_for(market_price, cost, rules) if market_price >= cost else None
        out["market_price"] = money_str(market_price)
        out["selling_price"] = money_str(sp) if sp is not None else None
        out["mp_margin_pct"] = _pct(margin_pct(market_price, cost))
        out["sp_margin_pct"] = _pct(margin_pct(sp, cost)) if sp is not None else None
        out["manual_market_price"] = True
    return out


def reprice(product: Product, rules: PricingRules) -> dict[str, list[Any]]:
    """Recompute the non-manual prices of one product in place. Returns the price diff."""
    cost = Decimal(product.cost_price)
    result = calculate(cost, rules, mp_mode=product.mp_round_mode)  # type: ignore[arg-type]
    before = {"market_price": product.market_price, "selling_price": product.selling_price}
    mp = Decimal(product.market_price) if product.mp_is_manual else result.market_price
    if product.sp_is_manual:
        sp = Decimal(product.selling_price)
    else:
        from core.pricing import selling_price_for

        sp = selling_price_for(mp, cost, rules)
    if not (cost <= sp <= mp):
        raise BusinessRuleError(
            f"{product.code}: prices would break cost ≤ SP ≤ MP "
            f"(cost {money_str(cost)}, SP {money_str(sp)}, MP {money_str(mp)}). "
            "Update the manual price or switch it back to auto.",
            code="PRICE_RULE_VIOLATION",
        )
    product.market_price, product.selling_price = mp, sp
    return audit_service.diff(
        before, {"market_price": product.market_price, "selling_price": product.selling_price}
    )


def apply_to_products(dry_run: bool, actor: ActorContext) -> dict[str, Any]:
    """Reprice every active product's non-manual prices with the current rules (admin)."""
    rules = get_rules()
    products = list(
        db.session.scalars(select(Product).where(Product.is_active).order_by(Product.id)).all()
    )
    diffs: list[dict[str, Any]] = []
    try:
        for product in products:
            if product.mp_is_manual and product.sp_is_manual:
                continue
            changes = reprice(product, rules)
            if changes:
                diffs.append(
                    {
                        "id": product.id,
                        "code": product.code,
                        "name": product.name,
                        "changes": changes,
                    }
                )
    except Exception:
        db.session.rollback()  # one bad product → nothing is changed
        raise

    if dry_run:
        db.session.rollback()
        return {"affected": len(diffs), "sample": diffs[:10], "applied": False}

    with transaction():
        for item in diffs:
            audit_service.record(
                actor,
                "product.reprice",
                "product",
                item["id"],
                f"{item['code']} {item['name']}: repriced by new pricing rules",
                changes=item["changes"],
                metadata={"trigger": "settings_apply"},
            )
        audit_service.record(
            actor,
            "pricing.apply",
            "pricing_settings",
            1,
            f"Applied pricing rules to {len(diffs)} product(s)",
            metadata={"affected_count": len(diffs)},
        )
    return {"affected": len(diffs), "sample": diffs[:10], "applied": True}
