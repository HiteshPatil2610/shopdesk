# UI Context — ShopDesk

Two apps with different jobs, so two different UI personalities:

| | Admin Console | Billing Counter |
|---|---|---|
| Goal | Accuracy, overview, control | **Speed**, few clicks, no mistakes |
| Device | Desktop/laptop (≥ 1280px), usable on tablet | Counter PC or tablet (≥ 1024px), touch-friendly |
| Input | Mouse + keyboard | **Keyboard and barcode scanner first**, touch second |
| Density | Medium (data tables) | Large text, big buttons, high contrast |

## 1. Design tokens (shared, in Tailwind config)

Both apps import the same `tailwind.preset.js` from `frontend/packages/shared`.

### Colours
| Token | Light | Dark | Use |
|---|---|---|---|
| `bg` | `#F8FAFC` | `#0F172A` | page background |
| `surface` | `#FFFFFF` | `#1E293B` | cards, tables, modals |
| `border` | `#E2E8F0` | `#334155` | dividers |
| `text` | `#0F172A` | `#F1F5F9` | primary text |
| `text-muted` | `#64748B` | `#94A3B8` | labels, hints |
| `primary` | `#2563EB` | `#3B82F6` | main actions, links |
| `success` | `#16A34A` | `#22C55E` | Confirm order, in stock |
| `danger` | `#DC2626` | `#EF4444` | Reject, delete, out of stock, errors |
| `warning` | `#D97706` | `#F59E0B` | low stock, manual price badge |
| `discount` | `#7C3AED` | `#A78BFA` | discount toggle on, savings line |

Dark mode: `class` strategy, a toggle in the user menu, defaults to the system setting. The **Billing Counter defaults to light** for readability under shop lighting.

### Typography
- Font: **Inter** (UI), **JetBrains Mono** (product codes, invoice numbers).
- Admin base size 14px. POS base size **16px**, cart rows 18px, grand total 32–40px bold.
- All numbers use `font-variant-numeric: tabular-nums` and are right-aligned in tables.

### Spacing, radius, shadow
- 4px spacing scale (Tailwind default). Card padding 16–24px.
- Radius: `rounded-lg` (8px) for inputs/cards, `rounded-xl` for modals.
- Shadows: `shadow-sm` on cards, `shadow-lg` on modals only.

### Money formatting (one helper, shared)
```ts
formatINR("1234.5") // "₹1,234.50"   → Intl.NumberFormat('en-IN', {style:'currency', currency:'INR'})
```
The API sends money as **strings** (`"300.00"`). Never `parseFloat` them for maths in the UI. The UI only displays what the server computed.

### Dates
Shown in IST: `04 Oct 2026, 5:42 PM`. Relative time ("3 min ago") only in the audit log, with the exact time in a tooltip.

## 2. Shared components (`frontend/packages/shared/ui`)

`Button` (variants: primary, secondary, success, danger, ghost; sizes sm/md/lg/xl) ·
`Input`, `NumberInput`, `MoneyInput` (₹ prefix, 2 decimals) · `Select` · `Toggle` ·
`Badge` (stock/status/manual) · `Modal` + `ConfirmDialog` · `DataTable` (sort, paginate, empty and loading states) ·
`Toast` (success/error, bottom-right) · `Spinner`/`Skeleton` · `EmptyState` · `ImageDropzone` · `Kbd` (shows shortcut keys) · `ErrorBoundary`.

Every async view has **loading, empty, error and success** states. No blank screens.

## 3. Admin Console screens

### 3.1 Layout
```
┌────────────┬──────────────────────────────────────────────────────┐
│ ShopDesk   │  Page title                     🔍 search   👤 Ravi ▾ │
│ ADMIN      ├──────────────────────────────────────────────────────┤
│            │                                                      │
│ ▣ Dashboard│                  page content                        │
│ ▣ Products │                                                      │
│ ▣ Stock    │                                                      │
│ ▣ Orders   │                                                      │
│ ▣ Audit Log│                                                      │
│ ▣ Pricing* │                                                      │
│ ▣ Users*   │                                                      │
│            │                                                      │
└────────────┴──────────────────────────────────────────────────────┘
 * admin role only (hidden for managers, and the API also blocks them)
```
Collapsible sidebar on screens narrower than 1024px.

### 3.2 Routes
| Route | Screen |
|---|---|
| `/sign-in` | ShopDesk-branded page hosting Clerk's `<SignIn />` (sign-up hidden). Styled with Clerk `appearance` variables that match the tokens in §1 |
| `/` | Dashboard |
| `/products` | Product list |
| `/products/new` | Add product |
| `/products/:id` | Edit product (tabs: Details · Stock history · Audit history) |
| `/stock` | Stock overview + adjust |
| `/orders`, `/orders/:id` | Orders list / detail |
| `/audit` | Audit log |
| `/settings/pricing` | Pricing settings |
| `/users` | User management |

### 3.3 Product list
- Toolbar: search (code/name/barcode), category filter, "Low stock only" toggle, "Show inactive" toggle, **+ Add Product** (primary).
- Columns: thumbnail 40px · **Code** (mono) · Name · Category · Qty (red badge if 0, amber if ≤ reorder level) · Cost · MP · SP · Margin % · Status · ⋯ actions.
- Click a row to open the edit page. Server-side pagination (25 per page).

### 3.4 Add / Edit product form
```
┌─────────────────────────────┬──────────────────────────────────┐
│  [ image dropzone 1:1 ]     │ Name*            [            ]  │
│  JPG/PNG/WebP (auto-resized)│ Category         [ select ▾   ]  │
│                             │ Unit             [ pcs ▾ ]       │
│                             │ Barcode          [            ]  │
│                             │ Quantity*        [   10 ]        │
│                             │ Reorder level    [    5 ]        │
├─────────────────────────────┴──────────────────────────────────┤
│ PRICING                                                        │
│ Cost price*  [ ₹ 212.00 ]                                      │
│ Market price [ ₹ 300.00 ] (auto)   ← 40% markup, rounded up ₹5 │
│ Selling price[ ₹ 265.00 ] (auto)   ← 25% markup, rounded up ₹5 │
│ Margin at MP: 41.5% · Margin at SP: 25.0%    [↻ Recalculate]   │
│ ⚠ SP must be ≥ cost and ≤ MP                                   │
├────────────────────────────────────────────────────────────────┤
│                                     [Cancel]  [Save product]   │
└────────────────────────────────────────────────────────────────┘
```
- Typing the cost calls `POST /api/pricing/preview` (debounced 300ms) and fills MP/SP **unless** that field was hand-edited.
- When a user edits MP or SP, show an amber **"manual"** badge with an ✕ to go back to auto.
- Inline validation mirrors BR-2. The Save button is disabled while the form is invalid.
- On edit, quantity is **read-only** with a link "Adjust stock →". Stock changes must go through the ledger with a reason.
- On 409 version conflict: modal "This product was changed by {user} at {time}. Reload?"

### 3.5 Stock adjust modal
Product (search) · Type (Restock + / Damage − / Correction ±) · Quantity · **Reason (required)** · shows `current → new`. Confirm button.

### 3.6 Orders
Table: Invoice no · Date/time · Customer · Cashier · Items · Discount (✓) · Total · Profit · Status (green Confirmed / grey Rejected). Filters: date range, cashier, status, customer search. Detail page: line items with snapshot prices + "View in audit log" link.

### 3.7 Audit log
```
Filters: [Date range] [User ▾] [Source: All|Admin|POS] [Action ▾] [Entity ▾] [🔍 search]   [⬇ CSV]
┌──────────────┬────────┬────────┬─────────────────┬───────────────────────────────────┐
│ When         │ User   │ Source │ Action          │ Summary                           │
├──────────────┼────────┼────────┼─────────────────┼───────────────────────────────────┤
│ 3 min ago    │ priya  │ POS    │ order.confirm   │ INV-20261004-0007 · Amit K · ₹865 │
│ 10 min ago   │ ravi   │ ADMIN  │ product.update  │ P00042 Steel bottle: MP 300 → 320 │
└──────────────┴────────┴────────┴─────────────────┴───────────────────────────────────┘
```
Clicking a row opens a side drawer with a full **diff view** (field · old in red · new in green), metadata, IP and user agent. Coloured action chips: create = green, update = blue, delete/deactivate = red, order = purple, auth = grey. The page is read-only and has no edit or delete controls.

### 3.8 Dashboard
KPI cards: Today's sales · Today's profit · Orders today (confirmed/rejected) · Low-stock count.
Charts: Sales last 14 days (bar) · Top 5 products this week (horizontal bar). List: low-stock items with a quick "Restock" button.

### 3.9 Pricing settings (admin)
MP markup %, SP markup %, Rounding mode (select), Rounding step. A **live example table** shows costs of ₹10, ₹99, ₹212 and ₹1,499 with the resulting MP/SP. A "Apply to all non-manual products" button opens a confirm dialog showing how many products will change.

## 4. Billing Counter screen (single page)

### 4.1 Layout
```
┌───────────────────────────────────────────────────────────────────────────────┐
│ ShopDesk · BILLING         Cashier: Priya        04 Oct 2026 17:42     [Logout]│
├───────────────────────────┬───────────────────────────────────────────────────┤
│ PRODUCTS        🔍 [     ]│ Customer name* [ Amit Kumar          ]  Phone [  ]│
│ ┌───────────────────────┐ │                                                   │
│ │🖼 P00042 Steel bottle │ │ Code [ P00042   ]  Qty [ 2 ]   [ Add ⏎ ]          │
│ │   ₹300 · 14 in stock  │ │───────────────────────────────────────────────────│
│ ├───────────────────────┤ │ # Code    Product        Qty   Unit     Total   ✕ │
│ │🖼 P00043 Lunch box    │ │ 1 P00042  Steel bottle  [-2+]  ₹300   ₹600.00  ✕ │
│ │   ₹450 · 3 in stock ⚠ │ │ 2 P00051  Notebook A5   [-1+]  ₹ 85   ₹ 85.00  ✕ │
│ ├───────────────────────┤ │                                                   │
│ │🖼 P00051 Notebook A5  │ │                                                   │
│ │   ₹85 · 0 OUT         │ │                                                   │
│ └───────────────────────┘ │───────────────────────────────────────────────────│
│  click = add to cart      │ Items: 3                 Subtotal (MP)   ₹685.00  │
│                           │ [ ◯ Apply Discount  F8 ]  Discount     − ₹  0.00  │
│                           │                           TOTAL         ₹685.00   │
│                           │                                                   │
│                           │  [ ✕ Reject  Esc ]          [ ✓ Confirm  F9 ]     │
└───────────────────────────┴───────────────────────────────────────────────────┘
```

### 4.2 Behaviour
- On load, focus goes to **Customer name**. Enter moves to **Code**, Enter moves to **Qty** (default 1), and Enter adds the line and returns focus to **Code**.
- **Barcode scanners** type the code and send Enter. Treat that as "add qty 1" straight away.
- Unknown code: red shake on the field, message "No product with code P0004". Out of stock: "Only 3 left".
- Adding an existing code increases that line's quantity.
- Line qty steppers can't go above available stock.
- **Apply Discount toggle** (purple when on): every line's unit price switches **MP → SP** with a short highlight. The Discount row shows `− ₹X` and "You save ₹X" appears.
- Totals always come from `POST /api/cart/quote` (debounced). While the quote is loading, show a small spinner beside TOTAL and disable Confirm.
- **Confirm** is disabled until there's a customer name and at least one valid line. Clicking it opens a summary dialog ("Confirm ₹865.00 for Amit Kumar? Payment: Cash/UPI/Card") → Enter confirms.
- **Reject** asks for confirmation ("Reject this order? Reason (optional)"), then clears the cart.
- After confirm: a **receipt modal** with Print (`window.print()` with a print stylesheet for 80mm thermal paper) and **New order (N)**, which resets the screen.
- 409 on confirm (stock changed): highlight the problem lines in red with "Only X available now". Nothing is saved.
- Network error: the cart is kept (in `sessionStorage`) and a retry banner appears. The same idempotency key is reused on retry.

### 4.3 Keyboard shortcuts (shown as `Kbd` hints)
| Key | Action |
|---|---|
| F2 | Focus product code |
| F3 | Focus product search |
| F4 | Focus customer name |
| F8 | Toggle discount |
| F9 | Confirm order |
| Esc | Reject / close modal |
| N | New order (on receipt modal) |
| ↑/↓ + Del | Select line / remove line |

### 4.4 Receipt (print)
```
          SHOP NAME
     address · phone
--------------------------------
Invoice: INV-20261004-0007
Date:    04-10-2026 17:45
Customer: Amit Kumar
Cashier:  Priya
--------------------------------
Steel bottle      2 x 265  530.00
Notebook A5       1 x  75   75.00
--------------------------------
Subtotal (MP)            685.00
Discount                 -80.00
TOTAL               ₹    605.00
Payment: UPI
     Thank you! Visit again
```

## 5. Accessibility and usability

- Every input has a visible `<label>`. Errors are linked with `aria-describedby`.
- Colour is never the only signal: pair it with an icon or text ("OUT", "manual", ✓).
- Contrast ≥ 4.5:1. POS totals ≥ 7:1.
- Focus ring visible on everything (`focus-visible:ring-2 ring-primary`).
- Touch targets ≥ 44px on POS.
- Confirm/Reject dialogs trap focus. Esc closes.

## 6. Frontend folder conventions

```
src/
├── main.tsx, App.tsx, routes.tsx
├── lib/            api.ts (axios instance: Clerk Bearer token + one retry on 401), queryClient.ts, prewarm.ts (one /api/health call on load), resizeImage.ts (admin: canvas → ≤1024px WebP before upload)
├── features/       products/, pricing/, audit/, cart/ … (hooks + components per feature)
│   └── products/
│       ├── api.ts          # useProducts(), useCreateProduct() (TanStack Query)
│       ├── ProductForm.tsx
│       └── schema.ts       # Zod
├── pages/          route-level components (thin, compose features)
├── components/     app-specific shared bits (Layout, Sidebar, …)
└── styles/         index.css (Tailwind layers), print.css
```
