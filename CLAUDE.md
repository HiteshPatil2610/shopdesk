# CLAUDE.md — ShopDesk

Product management + billing system: **Admin Console** (Flask admin_api + React admin-web) and **Billing Counter** (Flask pos_api + React pos-web), sharing one **Neon** Postgres database and a shared Python package `backend/core`. Auth is **Clerk**, images are **Cloudinary**, and hosting is **Vercel**: 4 projects. The two APIs run as Python serverless functions from `backend/`, and `SHOPDESK_SERVER=admin|pos` picks the app. Local dev ports: 5001/5002 (APIs), 5173/5174 (web).

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
- Each API verifies the Clerk token's signature, `azp` (its own frontend only) and role. Only the Clerk **publishable** key may appear in frontend code.
- Serverless rules: no in-memory state between requests, no local disk writes, no heavy work at import time, request bodies under 4 MB, and migrations backward-compatible (expand → contract).
- Apps use Neon's **pooled** URL, and migrations use the **direct** URL. Never point local commands at the Neon `main` (production) branch.
- Update `context/progress-tracker.md` at the end of every task.
