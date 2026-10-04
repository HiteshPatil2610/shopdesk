# Project Overview — ShopDesk

## 1. Problem

A small shop needs to:

1. Keep a clean catalogue of products with images, stock and cost price.
2. Turn a cost price into a sensible **Market Price (MP)** and **Selling Price (SP)** without doing the maths by hand each time.
3. Bill customers quickly at the counter, offer a discount when needed, and have stock update automatically.
4. Know **who changed what and when**, for both product edits and sales.

Today this is done by hand or in spreadsheets. That leads to pricing mistakes, wrong stock counts, and no record of who did what.

## 2. Solution summary

**Two web apps (servers), one shared database.**

```
┌──────────────────────┐        ┌──────────────────────┐
│  Admin Console       │        │  Billing Counter     │
│  (Server 1)          │        │  (Server 2)          │
│  owner / manager     │        │  cashier             │
└──────────┬───────────┘        └──────────┬───────────┘
           │                               │
           └──────────────┬────────────────┘
                          ▼
                ┌───────────────────┐
                │ PostgreSQL (one   │
                │ shared database)  │
                └───────────────────┘
```

They are separate servers so that:
- the cashier's machine **cannot reach** admin functions (cost prices, product editing, audit log), even by URL guessing
- each can be deployed, restarted and scaled on its own
- a problem in one does not take down the other

## 3. Users and roles

| Role | Admin Console | Billing Counter | Notes |
|---|---|---|---|
| **Admin** (owner) | Full access, including users and pricing settings | Yes | Only role that can create users and change pricing formula settings |
| **Manager** | Products, stock, orders, audit log (read) | Yes | Cannot manage users or global settings |
| **Cashier** | ❌ No access | Yes | Never sees cost price |

Sign-in is handled by **Clerk**, and public sign-up is switched off. The owner's account is created once in the Clerk dashboard and promoted to Admin. After that, the Admin creates every staff account (username + password) from the ShopDesk Users page.

**Platform:** everything runs on managed cloud services: **Vercel** (both websites and both API servers), Neon (database), Clerk (sign-in) and Cloudinary (images). Costs: a domain name, plus **Vercel Pro** once the shop uses it for real sales (Vercel's free plan is non-commercial). See [architecture.md](architecture.md).

## 4. Features

### 4.1 Admin Console (Server 1)

| Feature | Description |
|---|---|
| Login | Clerk sign-in (username + password). Only Admin or Manager roles can use this server |
| Product list | Search, filter by category or low stock, sort, paginate. Shows thumbnail, code, name, qty, cost, MP and SP |
| Add product | Image, name, category, unit, quantity, cost price. **MP and SP are auto-calculated live** as cost is typed, and both can be edited |
| Edit product | Every field is editable. If MP or SP was hand-edited it is marked *manual* and won't be overwritten when cost changes, unless you click "Recalculate" |
| Product code | Auto-generated (`P00001`). An optional barcode field allows scanning |
| Deactivate product | Soft delete only. A product that appears in past orders can never be hard-deleted |
| Stock adjustment | Restock (+), correction (±) or damage/loss (−), each with a required reason. Every change goes to the stock ledger |
| Pricing settings | Global MP markup %, SP markup %, rounding rule. Admin only |
| Orders | Read-only list of confirmed and rejected orders from the Billing Counter, with filters and order detail |
| **Audit log** | Every create, update, delete, price change, stock change, login, order confirm and order reject, with before/after values, the user, the time and the source server |
| Dashboard | Today's sales, profit, order count, low-stock items, top sellers |
| Users | Create, deactivate, reset password and set role. Admin only |

### 4.2 Billing Counter (Server 2)

| Feature | Description |
|---|---|
| Login | Clerk sign-in. Any active user (Cashier, Manager or Admin) |
| Product list panel | Searchable list of active products: image, code, name, MP, available stock. **No cost price** |
| Customer details | **Customer name is required** before confirming. Phone is optional |
| Add line | Type or scan a **product code**, enter a **quantity**, press Enter. The line shows `qty × MP = line total` with prices fetched from the DB |
| Same product twice | Adding a code that's already in the cart increases that line's quantity instead of adding a duplicate line |
| Edit/remove line | Change qty or remove a line before confirming |
| **Apply Discount** | A toggle at the bottom. When on, every line switches from **MP to SP** (the SP stored in the DB). The screen shows the amount saved |
| **Confirm order** | The server re-checks stock and prices, saves the order, **reduces stock** (4 in stock − 2 sold = 2), writes the audit log, and shows a receipt |
| **Reject order** | Clears the cart. The rejected cart is saved as a `rejected` order for traceability, and stock is **not** changed |
| Receipt | Printable receipt with an invoice number, customer name, cashier, lines and totals |
| Stock guard | You can't add more than the available quantity. On confirm, the server checks again in case another counter just sold the same item |

## 5. Business rules (must hold at all times)

| ID | Rule |
|---|---|
| BR-1 | Money is stored as `NUMERIC(12,2)` in the database and handled as `Decimal` in Python. **Never float.** Currency is INR (₹) |
| BR-2 | `cost_price ≤ selling_price ≤ market_price`. The server rejects any product save that breaks this |
| BR-3 | `quantity ≥ 0` always (enforced with a DB `CHECK` constraint). Overselling is impossible |
| BR-4 | Line total = unit price × quantity. Unit price is MP, or SP when discount is applied |
| BR-5 | **The server computes all prices and totals.** The Billing Counter sends only `code + qty + discount flag`. Prices sent by the browser are ignored |
| BR-6 | When an order is confirmed, the product prices at that moment are **copied into the order line** (snapshot). Later price edits never change past orders |
| BR-7 | Stock is decremented **atomically, inside one transaction**, with row locks. Either every line succeeds or nothing changes |
| BR-8 | Every change to products, prices, stock, settings, users or orders writes an audit row **in the same transaction**. If the audit write fails, the change fails |
| BR-9 | Audit log rows are **append-only**: no update or delete through the app, and blocked by a DB trigger too |
| BR-10 | Products are never hard-deleted once referenced by an order. Use `is_active = false` |
| BR-11 | Each order is confirmed at most once. An idempotency key stops a double click from creating two orders |
| BR-12 | Cost price and profit figures are never sent to the Billing Counter API |

## 6. Pricing formula (default)

The formula lives in **one function** (`backend/core/pricing.py`) so it can be swapped out easily. See [specs/04-pricing-engine.md](specs/04-pricing-engine.md).

```
raw_mp = cost × (1 + mp_markup_percent / 100)
raw_sp = cost × (1 + sp_markup_percent / 100)

MP = round_price(raw_mp)        # e.g. round UP to nearest ₹5
SP = round_price(raw_sp)

then enforce: cost ≤ SP ≤ MP
```

Default settings: `mp_markup = 40%`, `sp_markup = 25%`, rounding = **up to nearest ₹5**.
Example: cost ₹212 → raw MP 296.80 → **MP ₹300**, raw SP 265.00 → **SP ₹265**.

> ⚠️ **Open decision:** you said you'll apply "some math formula". Replace the default above with your real formula when it's ready. Only `pricing.py` and its tests need to change.

## 7. Improvements suggested on top of the original idea

These are already folded into the specs:

| # | Suggestion | Why |
|---|---|---|
| 1 | **Login and roles on both servers** | Without them, anyone on the network can edit prices or sell stock |
| 2 | **Server-side price calculation** (BR-5) | Stops someone editing the browser request to sell at ₹1 |
| 3 | **Row-locked atomic stock update** (BR-7) | Two counters selling the last item at the same time can't both succeed |
| 4 | **Price snapshot on order lines** (BR-6) | Old invoices stay correct after price changes |
| 5 | **Stock ledger** (`stock_movements`) | Every +/− to quantity is explained, so you can rebuild or audit stock |
| 6 | **Cashier also recorded** on every order, not just the customer | You know who sold it, not just who bought it |
| 7 | **Rejected orders saved** | Spots patterns like many rejected carts from one cashier |
| 8 | **Manual-override flag** on MP/SP | Recalculating from cost won't wipe a hand-set price |
| 9 | **Product codes + barcode support** | A USB barcode scanner works out of the box (it types like a keyboard) |
| 10 | **Cost price hidden from cashiers** (BR-12) | Protects margin information |
| 11 | **Low-stock alerts** (reorder level) | Restock before you run out |
| 12 | **Idempotent confirm** (BR-11) | Double click or a slow network won't create two orders |
| 13 | **Backups**: Neon point-in-time restore + nightly `pg_dump` via GitHub Actions | A bad migration or mistake shouldn't lose sales history |
| 14 | **Receipt printing** with invoice number | Proper record for the customer |
| 15 | Future: GST/tax, returns, customer table, multi-store | Kept out of v1 to stay shippable |

## 8. Scope

### In scope (v1)
Everything in sections 4–6, plus specs 01–10.

### Out of scope (v1, candidates for later)
- GST/tax invoices (HSN codes, CGST/SGST split)
- Returns and refunds (reversing an order and restoring stock)
- Per-line discount or custom % discount. v1 discount = switch to SP for the whole order
- Customer accounts, loyalty points, credit sales
- Supplier and purchase-order management
- Multiple shops or warehouses
- Online payments integration. v1 just records the sale; payment mode is a simple field (cash/UPI/card)
- Mobile apps

## 9. Success criteria

- A product can be added with an image, and MP/SP appear automatically in under a second.
- A cashier can bill a 5-item order in **under 30 seconds** using only the keyboard or scanner.
- After confirm, stock in the Admin Console is updated straight away, and the audit log shows the sale.
- Two counters selling the last unit at the same time: exactly one succeeds, and the other gets a clear "out of stock" message.
- No float money anywhere (checked in code review). All business rules BR-1 to BR-12 have automated tests.

## 10. Glossary

| Term | Meaning |
|---|---|
| **CP** | Cost price, what the shop paid |
| **MP** | Market price, the normal price charged |
| **SP** | Selling price, the discounted price used when "Apply Discount" is on. Always ≥ CP |
| **Product code** | Short unique ID such as `P00042`, typed or scanned at the counter |
| **Order** | One billing session: confirmed (stock reduced) or rejected (no stock change) |
| **Stock movement** | One row in the ledger explaining a change to a product's quantity |
| **Audit log** | Append-only history of every important action |
| **Source** | Which server an action came from: `admin`, `pos` or `system` |
