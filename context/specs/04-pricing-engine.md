# Spec 04 — Pricing Engine (MP / SP calculator)

**Status:** ⬜ Not started · **Depends on:** 01 (pure part), 03 (integration) · **Server(s):** Admin

## 1. Goal
Turn a cost price into a rounded **Market Price (MP)** and **Selling Price (SP)** with a configurable formula, show it live while typing, and let the admin change the formula settings and re-apply them to products.

## 2. User stories
- As a **manager**, when I type a cost price, I immediately see the MP and SP that will be used.
- As the **admin**, I change the markup % or rounding rule, preview the effect, and apply it to all products that don't have manual prices.
- As a **developer**, I can replace the formula in one place, and tests tell me if I broke a rule.

## 3. Scope
**In:** pure `core/pricing.py`, `pricing_settings` table, preview endpoint, settings get/put, bulk recalculate, settings UI with example table.
**Out:** per-category formulas (backlog: add `category.mp_markup_override` later), time-based offers, GST.

## 4. Business rules touched
BR-1, BR-2, BR-8. New:
- **PE-1** The formula is a **pure function**: `calculate(cost: Decimal, s: PricingSettings) -> PriceResult(mp, sp)`. No DB, no Flask.
- **PE-2** Output always satisfies `cost ≤ SP ≤ MP`. If rounding pushes SP above MP, set `SP = MP`. If SP < cost after rounding down, set `SP = round_up(cost)`.
- **PE-3** `0 ≤ sp_markup ≤ mp_markup ≤ 500`. `rounding_step ∈ {0.01, 0.50, 1, 2, 5, 10, 50, 100}`.
- **PE-4** Changing settings never changes existing product prices by itself. Only an explicit "Apply to products" action does, and it skips manual fields.

## 5. The formula (default — replace when the owner gives the real one)

```python
def calculate(cost: Decimal, s: PricingSettings) -> PriceResult:
    raw_mp = cost * (1 + s.mp_markup_percent / 100)
    raw_sp = cost * (1 + s.sp_markup_percent / 100)
    mp = round_price(raw_mp, s.rounding_mode, s.rounding_step)
    sp = round_price(raw_sp, s.rounding_mode, s.rounding_step)
    sp = min(sp, mp)                       # PE-2
    if sp < cost: sp = round_price(cost, "up", s.rounding_step)
    if mp < sp:  mp = sp
    return PriceResult(mp=q2(mp), sp=q2(sp))
```

**Rounding modes** (`round_price(value, mode, step)`):
| Mode | Rule | 296.80 with step 5 |
|---|---|---|
| `up` (default) | ceil to multiple of step | 300.00 |
| `nearest` | half-up to nearest multiple | 295.00 |
| `down` | floor to multiple | 295.00 |
| `ends_with_9` | ceil to a multiple of step (step ≥ 10), then −1. If that's below the raw value, add one step | step 10 → 299.00 |
| `none` | 2-decimal half-up | 296.80 |

**Worked examples** (mp 40%, sp 25%, up/5):
| Cost | raw MP | MP | raw SP | SP |
|---|---|---|---|---|
| 10.00 | 14.00 | 15.00 | 12.50 | 15.00 |
| 99.00 | 138.60 | 140.00 | 123.75 | 125.00 |
| 212.00 | 296.80 | 300.00 | 265.00 | 265.00 |
| 1499.00 | 2098.60 | 2100.00 | 1873.75 | 1875.00 |
| 0.00 | 0 | 0.00 | 0 | 0.00 |

(At cost 10 the SP rounds to 15 = MP. That's allowed, but the UI shows a hint: "discount gives no saving".)

These rows become a **parametrised unit test**. When the formula changes, update this table and the test together.

## 6. Data model changes
Migration `0004_pricing_settings`: table per architecture §5.4, seeded with one row (id=1) of defaults, plus `CHECK (id = 1)`.

## 7. API (Admin :5001)
| Method | Path | Role | Request → Response |
|---|---|---|---|
| POST | /api/pricing/preview | mgr+ | `{cost_price: "212.00", settings?: {...}}` → `{market_price, selling_price, mp_margin_pct, sp_margin_pct, explanation: "212 × 1.40 = 296.80 → up to ₹5 → 300"}`. Optional `settings` lets the settings page preview unsaved values |
| GET | /api/pricing/settings | mgr+ | current settings |
| PUT | /api/pricing/settings | admin | full settings → audit `pricing_settings.update` with diff |
| POST | /api/pricing/apply | admin | `{dry_run: true}` → `{affected: 37, sample: [...first 10 diffs]}`. `{dry_run: false}` → updates all **active** products' non-manual MP/SP in one transaction, bumps each `version`, writes **one** audit row per changed product (`product.reprice`) plus a summary row `pricing.apply` |
| POST | /api/products/{id}/recalculate-prices | mgr+ | `{reset_manual: bool}`. Recalculates one product. If `reset_manual`, both flags are cleared first |

## 8. UI
- **Product form** (spec 03): debounced preview call. A small "ⓘ" tooltip shows `explanation`. Margin % is shown under the prices.
- **Pricing settings page** (ui-context §3.9): form + live examples table (preview with unsaved settings) + "Save" + "Apply to products…" (dry-run modal showing the count and a sample diff table → Confirm).

## 9. Tasks
- [ ] 1. `core/pricing.py` + `round_price` + `PriceResult`. Exhaustive unit tests including the examples table and property-style tests (random costs 0–100000, assert PE-2 always holds).
- [ ] 2. `PricingSettings` model + migration + seed.
- [ ] 3. `pricing_service`: `get_settings`, `update_settings` (validate PE-3, audit), `preview`, `apply_to_products(dry_run)`, `recalculate_product`.
- [ ] 4. Routes.
- [ ] 5. Wire into `product_service.create/update` (spec 03).
- [ ] 6. Settings page + preview in the product form.
- [ ] 7. Tests.

## 10. Acceptance criteria
- [ ] All rows of the worked-examples table pass as unit tests.
- [ ] 10,000 random costs × every rounding mode → `cost ≤ SP ≤ MP` always (property test).
- [ ] A manager can preview but gets 403 on PUT settings and apply.
- [ ] Apply with dry_run shows the count. Real apply changes only non-manual fields of active products and writes audit rows.
- [ ] Changing settings alone doesn't change any product price (PE-4).
- [ ] No `float` in `pricing.py` (enforced with a ruff/grep check in CI).

## 11. Tests
- Unit: rounding modes at boundaries (exact multiples, 0, 0.01, very large), PE-2 clamps.
- Service: apply skips manual and inactive, version bumps, audit counts.
- API: roles, preview with custom settings.

## 12. Open questions
- **Q1:** the owner's real formula. Only §5, `pricing.py` and its tests change.
