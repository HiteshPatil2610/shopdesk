# Spec 04 — Pricing Engine (MP / SP calculator)

**Status:** ✅ Built (2026-10-04) · **Depends on:** 01 (pure part), 03 (integration) · **Server(s):** Admin

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

## 5. The formula (owner's rules, 2026-10-04)

```
markup  = 95% if cost < ₹500 else 90%                      (markup_low_pct / markup_high_pct / markup_threshold)
raw_mp  = cost × (1 + markup/100)
MP      = round UP raw_mp:
            raw_mp ≥ ₹500 → next ₹50  (default)  or next ₹100 (bigger option)   (mp_step / mp_alt_step)
            raw_mp < ₹500 → next ₹10  (default)  or next ₹50  (bigger option)   (small_mp_*)
          the product stores which option was chosen (mp_round_mode = primary | alternate)
SP      = MP − 10%, rounded DOWN to the nearest ₹10        (sp_discount_pct / sp_step)
clamp   : cost ≤ SP ≤ MP
```
Owner's examples: MP 1243 → **1250**; 1412 → **1450** or **1500** (choice in the UI); SP 1293 → **1290**.
*Note:* the owner also wrote "SP 1212 → 1200", but the rule "closest lower number ending in 0" gives **1210**. The code follows the rule. Set `sp_step = 100` if hundreds were meant.
*Note:* because the markup drops at ₹500, cost ₹499 → MP ₹1000 but cost ₹500 → MP ₹950. This is how the rule works. Tell us if you want it smoothed.

**Worked examples** (unit-tested in `tests/unit/test_pricing.py`):
| Cost | raw MP | MP (default) | MP (bigger) | SP |
|---|---|---|---|---|
| 20 | 39.00 | 40.00 | 50.00 | 30.00 |
| 212 | 413.40 | 420.00 | 450.00 | 370.00 |
| 499 | 973.05 | 1000.00 | — | 900.00 |
| 500 | 950.00 | 950.00 | 1000.00 | 850.00 |
| 650 | 1235.00 | 1250.00 | 1300.00 | 1120.00 |
| 743 | 1411.70 | 1450.00 | 1500.00 | 1300.00 (bigger MP → 1350.00) |
| 0 | 0.00 | 0.00 | — | 0.00 |

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
- [x] 1. `core/pricing.py` + `round_price` + `PriceResult`. Exhaustive unit tests including the examples table and property-style tests (random costs 0–100000, assert PE-2 always holds).
- [x] 2. `PricingSettings` model + migration + seed.
- [x] 3. `pricing_service`: `get_settings`, `update_settings` (validate PE-3, audit), `preview`, `apply_to_products(dry_run)`, `recalculate_product`.
- [x] 4. Routes.
- [x] 5. Wire into `product_service.create/update` (spec 03).
- [x] 6. Settings page + preview in the product form.
- [x] 7. Tests.

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
- ~~Q1: owner's formula~~ Done (§5). Open: confirm SP 1212 → 1210 (rule) vs 1200 (example), and the ₹499/₹500 MP jump.
