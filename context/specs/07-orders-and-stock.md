# Spec 07 — Orders (Confirm / Reject) & Stock

**Status:** ⬜ Not started · **Depends on:** 05, 06 · **Server(s):** POS (confirm/reject/receipt), Admin (orders view, stock adjust)

## 1. Goal
When the cashier clicks **Confirm**, the order is saved with a price snapshot, stock is reduced **atomically** (4 − 2 = 2), the stock ledger and audit log are written, and a receipt is shown. **Reject** saves the cart as a rejected order without touching stock. Admins can view orders and adjust stock with a reason.

## 2. User stories
- As a **cashier**, I confirm the order and get a printable receipt with an invoice number.
- As a **cashier**, if someone at another counter just bought the last unit, I get a clear message and nothing is half-saved.
- As a **cashier**, I reject an order and the screen clears. Stock doesn't change.
- As a **manager**, I see all confirmed and rejected orders with customer, cashier and totals.
- As a **manager**, I restock or correct quantities with a reason, and every change is in the ledger.

## 3. Scope
**In:** `orders`, `order_items`, invoice numbering, `order_service.confirm/reject`, idempotency, row locking, `stock_service.adjust`, stock ledger, receipt endpoint + print view, admin orders list/detail, admin stock adjust UI, "my orders today" on POS.
**Out:** returns/refunds/void (backlog B1), payments integration.

## 4. Business rules touched
BR-3, BR-5, BR-6, BR-7, BR-8, BR-11, BR-12. New:
- **OS-1** Invoice number `INV-YYYYMMDD-NNNN`, with NNNN resetting daily (IST). Generated inside the confirm transaction using a `daily_counters` row with `SELECT … FOR UPDATE` (or a Postgres sequence per day). Must be unique and gap-tolerant.
- **OS-2** Rejected orders use their own prefix `REJ-YYYYMMDD-NNNN` and never consume an invoice number.
- **OS-3** Stock adjustments need a reason (`restock`, `damage`, `correction`) and a note for `correction`/`damage`. The result must be ≥ 0.
- **OS-4** `products.quantity` always equals `SUM(stock_movements.change)` for that product.

## 5. Data model changes
Migration `0006_orders`: `orders`, `order_items` (architecture §5.5–5.6), `daily_counters(counter_date DATE, kind VARCHAR, last_value INT, PK(counter_date, kind))`.

## 6. API

### POS (:5002, cashier+)
**`POST /api/orders/confirm`**
```json
{ "idempotency_key": "6f1c…uuid", "customer_name": "Amit Kumar", "customer_phone": "9876543210",
  "payment_mode": "upi", "discount_applied": true,
  "items": [ {"code": "P00042", "qty": 2}, {"code": "P00051", "qty": 1} ] }
```
→ **201** `{ order: {order_number, status:"confirmed", customer_name, cashier_name, created_at, discount_applied, payment_mode, lines:[{code,name,qty,unit_price,line_total}], item_count, subtotal_mp, discount_amount, total} }`
→ **200** with the same body if `idempotency_key` was already confirmed (no new writes).
→ **409 `INSUFFICIENT_STOCK`** `details: [{code, requested, available}]` (nothing written).
→ **422 `PRODUCT_UNAVAILABLE`** if a code is unknown or inactive.
→ 400 validation (missing customer name, empty items, …).

**Transaction (must match architecture §6.3 exactly):**
1. Look up the idempotency key → return the existing order if found.
2. Merge duplicate codes. `BEGIN`.
3. `SELECT … FROM products WHERE code IN (…) AND is_active ORDER BY id FOR UPDATE`.
4. Check every line's qty ≤ quantity. Collect **all** failures, then roll back with 409.
5. Compute prices from the locked rows (MP or SP by flag). Snapshot cost/MP/SP.
6. Next invoice number (OS-1). Insert order + items.
7. For each product: `quantity -= qty` and insert `stock_movements(reason='sale', change=-qty, quantity_after, reference=order)`.
8. `audit_service.record('order.confirm', …)`.
9. `COMMIT`. If the commit races on `idempotency_key` UNIQUE, catch the IntegrityError and return the existing order.

**`POST /api/orders/reject`**: `{idempotency_key, customer_name?, discount_applied, items, reason?}` → 201 `{order_number: "REJ-…", status: "rejected"}`. Prices are snapshotted with **no lock and no stock change**. Audit `order.reject`. Unknown codes are skipped (noted in metadata) instead of failing.

**`GET /api/orders/{order_number}/receipt`**: receipt JSON (shop details from env + order). A cashier can only fetch their own orders from the last 24h. Managers and admins can fetch any.

**`GET /api/orders/mine?date=today`**: the cashier's own orders (number, time, customer, total, status) for an end-of-shift check.

### Admin (:5001, mgr+)
| Method | Path | Notes |
|---|---|---|
| GET | /api/orders | filters `from, to, status, cashier_id, q (customer/order no)`, includes `total_cost` and `profit` |
| GET | /api/orders/{id} | lines with snapshot prices and profit per line |
| POST | /api/stock/{product_id}/adjust | `{type: "restock"\|"damage"\|"correction", qty: int, note?: str, version?: int}`. restock → +qty, damage → −qty, correction → ±qty (signed). Locks the row. Result ≥ 0 else 422 `NEGATIVE_STOCK`. Ledger + audit `stock.adjust` |
| GET | /api/stock/{product_id}/movements | paginated ledger |
| GET | /api/stock/verify | admin only. Checks OS-4 for all products and returns mismatches (should be empty) |

## 7. UI
- **POS:** Confirm dialog (summary + payment mode radio: Cash/UPI/Card, default Cash) → on 201, receipt modal (ui-context §4.4) with Print (`print.css` for 80mm) and New order (N). On 409, close the dialog and mark the problem lines. Reject dialog with an optional reason. "My orders today" drawer from the header.
- **Idempotency key:** generated (`crypto.randomUUID()`) when the cart gets its first line, stored with the cart in sessionStorage, reused on retries, and replaced after a successful confirm/reject.
- **Admin:** Orders list + detail (ui-context §3.6). Stock page: products table with qty and "Adjust" buttons → adjust modal (ui-context §3.5). Product edit page "Stock history" tab lists movements.

## 8. Tasks
- [ ] 1. Models + migration (`Order`, `OrderItem`, `DailyCounter`).
- [ ] 2. `stock_service`: `apply_movement(session, product, change, reason, ref, actor)` (the **only** code that changes `quantity`), `adjust(...)`, `verify()`.
- [ ] 3. `order_service.confirm` per §6 with locking and idempotency. `reject`. `next_number(kind)`.
- [ ] 4. POS routes (confirm, reject, receipt, mine).
- [ ] 5. Admin routes (orders list/detail, stock adjust/movements/verify).
- [ ] 6. POS UI: confirm dialog, receipt modal + print CSS, reject dialog, 409 handling, idempotency key handling, my-orders drawer.
- [ ] 7. Admin UI: orders pages, stock page + adjust modal, stock history tab.
- [ ] 8. Tests, including **concurrency**.

## 9. Acceptance criteria
- [ ] Product with qty 4. Confirm an order for 2 → product qty 2, one `stock_movements(-2, sale, quantity_after=2)`, one order with snapshot prices, one `order.confirm` audit row.
- [ ] **Concurrency:** product qty 1, two threads confirm qty 1 at the same moment → exactly one 201 and one 409. Final qty 0. Never negative.
- [ ] Order with 3 lines where line 3 lacks stock → 409 listing line 3. Quantities of lines 1–2 **unchanged**, and no order row.
- [ ] Sending the same `idempotency_key` twice → one order. The second response is 200 with the same order number.
- [ ] After a confirmed sale, changing the product's MP in admin doesn't change the old order's totals or receipt.
- [ ] Reject → order `REJ-…` saved with status rejected. Quantities unchanged. Audit `order.reject` with customer name.
- [ ] Invoice numbers are sequential per day, and the first order after midnight IST is `…-0001`.
- [ ] Stock adjust "damage 3" on qty 2 → 422 `NEGATIVE_STOCK`.
- [ ] `/api/stock/verify` returns no mismatches after the full test suite.
- [ ] POS order/receipt responses contain no cost or profit fields.

## 10. Tests
- Service: confirm happy path, discount totals, multi-line rollback, idempotency (sequential + racing), reject, invoice numbering across a date boundary (freezegun), adjust types, verify invariant.
- **Concurrency test:** real Postgres, two `threading.Thread`s with separate sessions and a `Barrier` so both start together.
- API: roles, receipt access rules, validation, response field exposure.
- Frontend: 409 marks lines, key reuse on retry, receipt print layout snapshot.

## 11. Open questions
- Q7: require a reject reason? Default optional.
- Should a manager be able to **void** a confirmed order (restores stock)? Proposed as a backlog spec (B1).
