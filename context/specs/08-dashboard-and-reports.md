# Spec 08 — Dashboard & Reports

**Status:** ✅ Built (2026-10-05) · **Depends on:** 07 · **Server(s):** Admin

## 1. Goal
Give the owner a one-glance view of today's business (sales, profit, orders, low stock) and simple reports they can export.

## 2. User stories
- As the **owner**, I open the Admin Console and immediately see today's sales and profit.
- As the **owner**, I see which products are running low and restock them in one click.
- As the **owner**, I export sales for a date range to CSV for my accountant.

## 3. Scope
**In:** summary KPIs, sales-by-day chart, top products, low-stock list, sales CSV export, cashier summary.
**Out:** forecasting, custom report builder, PDF reports.

## 4. Business rules touched
BR-1 (all sums in SQL `NUMERIC`), BR-12 (admin only). Only **confirmed** orders count towards sales and profit. Rejected orders are shown as a separate count. Days are IST calendar days.

## 5. Data model changes
None. Add indexes if needed: `orders(status, created_at)`, `order_items(product_id)`.

## 6. API (Admin :5001, mgr+)
| Method | Path | Response |
|---|---|---|
| GET | /api/reports/summary?date=YYYY-MM-DD | `{sales_total, profit_total, discount_total, orders_confirmed, orders_rejected, items_sold, avg_order_value, low_stock_count, out_of_stock_count}` |
| GET | /api/reports/sales-by-day?from=&to= | `[{date, sales_total, profit_total, orders}]` (max 366 days, zero-filled) |
| GET | /api/reports/top-products?from=&to=&limit=5&by=qty\|revenue | `[{code, name, qty, revenue, profit}]` |
| GET | /api/reports/low-stock | `[{id, code, name, quantity, reorder_level}]` sorted by quantity/reorder_level |
| GET | /api/reports/cashiers?from=&to= | `[{cashier, orders, sales_total, rejected, discounts_given}]` |
| GET | /api/reports/sales.csv?from=&to= | one row per order line (date, invoice, customer, cashier, code, name, qty, unit price, line total, cost, profit, discount flag). Audit `report.export` |

Profit = `Σ (unit_price_charged − unit_cost) × qty` from **snapshots** in `order_items`.

## 7. UI
Dashboard per ui-context §3.8: 4 KPI cards (with "vs yesterday" ▲▼ %), 14-day sales bar chart (Chart.js), top-5 products bar, low-stock table with a "Restock" button that opens the stock adjust modal from spec 07. Date picker for viewing another day. Reports page: date range + Export CSV + cashier summary table. Auto-refresh every 60 s (TanStack Query `refetchInterval`).

## 8. Tasks
- [x] 1. `report_service` with SQL aggregation (SQLAlchemy core, `func.sum`, `date_trunc` at `Asia/Kolkata`).
- [x] 2. Routes + CSV streaming (same formula-injection escaping as spec 05).
- [x] 3. Dashboard page + charts (follow the dataviz palette; accessible colours, tooltips with ₹ formatting).
- [x] 4. Reports page.
- [x] 5. Tests with seeded orders across dates and statuses.

## 9. Acceptance criteria
- [x] Seed: 3 confirmed orders today (₹605, ₹300, ₹85) + 1 rejected → summary sales ₹990.00, orders 3 confirmed / 1 rejected. *(test)*
- [x] Profit uses snapshot cost. Changing a product's cost later doesn't change past profit. *(test)*
- [x] An order at 23:59 IST and one at 00:01 IST fall on different days. *(test)*
- [x] Low-stock list includes a product with qty 2 and reorder 5, and excludes inactive products. *(test)*
- [x] Cashier role gets no access (it's not even routed on POS). *(test)*

## 10. Tests
Service aggregation correctness, timezone boundary, CSV columns and escaping, role checks.

## 11. Implementation notes (2026-10-05)
- `summary` also returns `previous` (the day before) and server-computed `change_pct` for sales, profit and orders, so the browser does no money maths.
- Day grouping uses `timezone('Asia/Kolkata', created_at)::date` in SQL. Ranges are inclusive IST dates, default the last 14 days, max 366.
- The sales CSV is **admin-only** (financial data, consistent with the audit export), formula-safe, has a BOM for Excel, and is audited as `report.export`.
- Charts: Chart.js single-series bars in the validated chart hue (`--color-chart-1`, light/dark), 4px rounded ends, recessive grid, ₹ tooltips and a "Show as table" view. Admin pages are lazy-loaded so the chart library only loads with Dashboard/Reports.
