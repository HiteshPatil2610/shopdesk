# CLAUDE.md — ShopDesk

Product management + billing system: one Flask `shopdesk` app and one React `frontend/web` app, with separate Admin Console (`/admin`) and Billing Counter (`/pos`) areas. Shared business logic stays in `backend/core`; Neon is the database, Clerk handles auth, Cloudinary stores images. One Vercel project at repository root serves the SPA and `/api/*`. Local development: API 5001, web 5173.

**Before doing anything, read:**
1. `context/README.md`
2. `context/ai-workflow-rules.md` (hard rules H1–H14 are non-negotiable)
3. `context/progress-tracker.md` (current phase, open questions, next task)
4. The relevant `context/specs/NN-*.md`
5. `SETUP_GUIDE.md` for anything about env vars, accounts or keys

The most important rules:
- Money is `Decimal` / `NUMERIC(12,2)` / JSON strings. Never float.
- The server computes all prices and totals. The browser only sends code + qty + discount flag.
- Every write goes through a `core/services/*` function that runs in one transaction and writes an audit row.
- Stock changes only through `stock_service` (ledger row for every change). Sales lock rows with `FOR UPDATE`.
- POS API responses never include cost price or profit.
- The API verifies the Clerk token's signature, `azp` against `AUTHORIZED_PARTIES`, and the route's role plus area ceiling. Every admin route must refuse a cashier. Only the Clerk **publishable** key may appear in frontend code.
- Serverless rules: no in-memory state between requests, no local disk writes, no heavy work at import time, request bodies under 4 MB, and migrations backward-compatible (expand → contract).
- Apps use Neon's **pooled** URL, and migrations use the **direct** URL. Never point local commands at the Neon `main` (production) branch.
- Update `context/progress-tracker.md` at the end of every task.
