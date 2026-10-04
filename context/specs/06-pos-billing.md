# Spec 06 — POS Billing Screen (cart, quantity, discount)

**Status:** ✅ Built · live five-item speed check pending stocked catalogue · **Depends on:** 02, 03, 04 · **Server(s):** POS

## 1. Goal
A fast, keyboard-first billing screen. The cashier enters the customer name, adds products by code (typed or scanned) with quantity, sees the server-computed line totals at MP, toggles **Apply Discount** to switch every line to SP, and gets the cart ready for Confirm/Reject (spec 07).

## 2. User stories
- As a **cashier**, I type `P00042`, qty `2`, press Enter, and see `2 × ₹300 = ₹600`.
- As a **cashier**, I scan a barcode and the product is added with qty 1. Scanning again makes it qty 2.
- As a **cashier**, I click **Apply Discount** and every price changes to the selling price, with the saving shown.
- As a **cashier**, I'm stopped from adding more than the available stock.

## 3. Scope
**In:** billing page layout (ui-context §4), cart state (reducer + sessionStorage), lookup, product panel integration, **quote endpoint**, discount toggle, keyboard shortcuts, validation, error states.
**Out:** persisting orders and stock changes (spec 07), receipts (spec 07), custom % discounts (backlog).

## 4. Business rules touched
BR-4, BR-5, BR-12. New:
- **PB-1** The cart holds only `{code, qty}` + display info. **Every price on screen comes from the latest `/api/cart/quote` response.**
- **PB-2** Duplicate codes merge into one line (qty summed).
- **PB-3** Line qty: 1 ≤ qty ≤ min(available stock, 10,000).
- **PB-4** The discount flag applies to the **whole order**. When on, `unit_price = SP` for every line, otherwise `MP`.
- **PB-5** Customer name is 2–120 characters and required before Confirm. Phone is optional (10 digits if given, Indian mobile format).

## 5. Data model changes
None. Quote is read-only.

## 6. API (POS :5002, cashier+)
### `POST /api/cart/quote`
Request:
```json
{ "discount_applied": true, "items": [ {"code": "P00042", "qty": 2}, {"code": "P00051", "qty": 1} ] }
```
Response 200:
```json
{
  "discount_applied": true,
  "lines": [
    { "code": "P00042", "name": "Steel bottle", "thumb_url": "https://res.cloudinary.com/<cloud>/image/upload/c_fill,w_256,h_256,f_auto,q_auto/shopdesk/products/…",
      "qty": 2, "available": 14, "unit_mp": "300.00", "unit_sp": "265.00",
      "unit_price": "265.00", "line_total": "530.00", "status": "ok" },
    { "code": "P00051", "name": "Notebook A5", "qty": 1, "available": 9,
      "unit_mp": "85.00", "unit_sp": "75.00", "unit_price": "75.00", "line_total": "75.00", "status": "ok" }
  ],
  "item_count": 3,
  "subtotal_mp": "685.00",
  "discount_amount": "80.00",
  "total": "605.00",
  "can_confirm": true
}
```
Line `status`: `ok` · `not_found` · `inactive` · `insufficient_stock` (with `available`). `can_confirm` is false if any line isn't `ok` or the cart is empty.
Max 100 lines. 400 on bad input. The quote **never** returns cost.

### Uses from spec 03
`GET /api/products` (panel) and `GET /api/products/lookup?code=`.

## 7. UI behaviour
Exactly per ui-context §4.1–4.3. Implementation notes:
- `cartReducer` actions: `ADD(code, qty)`, `SET_QTY(code, qty)`, `REMOVE(code)`, `TOGGLE_DISCOUNT`, `SET_CUSTOMER(name, phone)`, `RESET`. Quotes remain server state in TanStack Query; they are never copied into persisted cart state.
- Cart state is mirrored to `sessionStorage` (`sd_pos_cart`), so a refresh doesn't lose the bill. It's cleared on confirm or reject.
- **Add flow:** `lookup(code)` → if found and enough stock, `ADD`, otherwise show an inline error. Then `quote` (debounced 150ms, latest-wins: cancel the in-flight request with AbortController).
- **Barcode detection:** a code field input that ends with Enter within < 50ms between keystrokes is treated as a scan → qty 1, add straight away.
- The discount toggle shows the "You save ₹X" chip (from `discount_amount`) when on. Lines animate the price change.
- Totals area shows a skeleton/spinner while a quote is pending. Confirm is disabled until the latest quote is back with `can_confirm`.
- Problem lines are red with a reason text ("Only 3 left", "No longer sold").
- Product panel: search (debounced 250ms), shows MP and stock badge. Out-of-stock items are greyed out and can't be clicked.

## 8. Tasks
- [x] 1. `order_service.quote(items, discount_applied)` in `core`: loads products by code in one query, computes lines with `Decimal`, merges duplicates (PB-2), flags statuses. Unit + service tests.
- [x] 2. `POST /api/cart/quote` route + Pydantic schemas (`QuoteRequest`, `QuoteResponse`, `QuoteLine`).
- [x] 3. POS-web billing page layout (header, product panel, customer section, entry row, cart table, totals, action bar).
- [x] 4. Cart reducer + sessionStorage persistence + tests.
- [x] 5. Lookup + add flow + barcode detection.
- [x] 6. Quote integration (debounce, abort, loading state) + discount toggle.
- [x] 7. Keyboard shortcuts (F2/F3/F4/F8/F9/Esc, arrows, Del) with a `useHotkeys` hook. `Kbd` hints.
- [x] 8. Validation: customer name/phone, qty bounds. Disabled states.
- [x] 9. Tests.

## 9. Acceptance criteria
- [x] With Steel bottle (MP 300 / SP 265, stock 14) and Notebook (85 / 75, stock 9): adding P00042 ×2 and P00051 ×1 shows subtotal ₹685.00. Toggling discount shows total ₹605.00 and discount ₹80.00.
- [x] Adding P00042 again with qty 3 → one line with qty 5, not two lines.
- [x] Qty 20 for a product with 14 in stock → blocked in the UI. If forced through the API, the quote line is `insufficient_stock` and `can_confirm` is false.
- [x] Unknown code → inline error, and the cart doesn't change.
- [x] A cashier who edits the request in DevTools to add `"unit_price": "1.00"` → ignored, and the response still uses DB prices.
- [x] Refreshing the page keeps the cart and customer name.
- [ ] A full 5-item bill can be keyed using only the keyboard (manual test, timed under 30s). Live catalogue is empty; timed check remains pending.
- [x] The quote response JSON contains no `cost` key.

## 10. Tests
- Unit/service: quote maths (MP vs SP, multiple lines, merging, rounding to 2 decimals), status flags, large qty bounds.
- API: role, validation (qty 0, negative, > 10,000, 101 lines), extra fields ignored.
- Frontend: reducer actions, barcode detection helper, discount toggle re-quotes, Confirm disabled states.

## 11. Open questions
- Q2: manager PIN for discount? Default no.

## Implementation notes (2026-10-04)
- Quote API and billing UI are built. Quotes use one product query, merged quantities and Decimal totals; client price fields are ignored. Combined duplicate quantity above 10,000 returns 400.
- F9 currently opens **Review bill**. **Clear bill** clears only a local draft after confirmation. Confirm/payment, persisted rejection, stock deductions and receipts arrive in spec 07.
- Session storage contains customer inputs and cart code/quantity/display data only. Restored drafts always fetch fresh prices. Request cancellation and separate query keys prevent old responses from displaying current totals.
- Browser verified authenticated empty state, unknown code rejection and customer recovery after refresh. Example totals, duplicate merge, stock limits, discount re-quote and persisted cart are automated tests; live stocked-cart speed check remains pending.

