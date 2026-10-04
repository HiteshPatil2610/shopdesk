# Progress Tracker — ShopDesk

> Update this file at the **end of every work session**. It's the first thing read at the start of the next one.

**Current phase:** Phase 1 ✅ (specs 01–02 done) → next: **spec 03 + 04 (products + pricing)**
**Last updated:** 2026-10-04

## Status overview

| Phase | Spec | Status | Notes |
|---|---|---|---|
| 0 | Context docs | ✅ Done | This folder |
| 1 | [01 Project setup](specs/01-project-setup.md) | ✅ Done | Both APIs + both web apps run against Neon. 36 backend + 9 frontend tests |
| 1 | [02 Authentication](specs/02-authentication.md) | ✅ Done | Owner verified sign-in, user creation and cashier blocking on 2026-10-04 |
| 2 | [03 Product management](specs/03-product-management.md) | ⬜ Not started | |
| 2 | [04 Pricing engine](specs/04-pricing-engine.md) | ⬜ Not started | Needs the owner's final formula (Q1) |
| 2 | [05 Audit log](specs/05-audit-log.md) | 🟨 Partly done | Table, trigger and `audit_service` built in spec 02. Viewer + CSV still to do |
| 3 | [06 POS billing](specs/06-pos-billing.md) | ⬜ Not started | |
| 3 | [07 Orders & stock](specs/07-orders-and-stock.md) | ⬜ Not started | |
| 4 | [08 Dashboard & reports](specs/08-dashboard-and-reports.md) | ⬜ Not started | |
| 4 | [09 Security hardening](specs/09-security-hardening.md) | ⬜ Not started | |
| 4 | [10 Deployment](specs/10-deployment.md) | ⬜ Not started | |

Legend: ⬜ Not started · 🟨 In progress · ✅ Done · ⛔ Blocked

## Milestones

- [x] **M1: Skeleton runs.** Both APIs return `/api/health`, both React apps load, Postgres is migrated (spec 01)
- [x] **M2: Secure login** on both servers with roles (spec 02)
- [ ] **M3: Catalogue.** Add/edit products with images and auto MP/SP, with everything audited (specs 03–05)
- [ ] **M4: First sale.** Bill → discount → confirm → stock reduced → audit row (specs 06–07)
- [ ] **M5: Owner insights.** Dashboard, low stock, CSV export (spec 08)
- [ ] **M6: Production-ready.** Hardened, backed up, deployed on Vercel (4 projects) + Neon `main` + Clerk production (specs 09–10)

## Current sprint / next up

0. Owner: create the GitHub, Neon, Clerk and Cloudinary accounts and fill `.env` (SETUP_GUIDE §3–§8, checklist §14)
1. Spec 01, tasks 1–5: repo skeleton, config, Neon-aware `core/db.py`, both Flask apps with health checks
2. Spec 01, tasks 5–7: both Vite apps with proxy, shared package, dev script

## Open questions (need the owner's answer)

| # | Question | Default if no answer | Status |
|---|---|---|---|
| Q1 | What's the exact MP/SP formula? | MP = cost × 1.40, SP = cost × 1.25, both rounded **up** to nearest ₹5 | Open |
| Q2 | Should "Apply Discount" need a manager PIN? | No. Any cashier can apply it, and it's audited | Open |
| Q3 | Shop name/address/phone for receipts? | Set in `.env` (`SHOP_NAME`, …) | Open |
| Q4 | Are fractional quantities needed (e.g. 1.5 kg)? | No. Integers only in v1 | Open |
| Q5 | Is GST needed on receipts? | Not in v1 | Open |
| Q6 | ~~Where will the servers run?~~ | Vercel (all 4 projects) + Neon + Clerk + Cloudinary | ✅ Decided 2026-10-04 |
| Q7 | Must a rejected order have a reason? | Optional | Open |
| Q8 | Which domain name? (needed for the Clerk production instance, spec 10) | Buy before spec 10. Use the Clerk dev instance until then | Open |
| Q9 | When will the Vercel team move from Hobby (non-commercial) to **Pro**? | Build/test on Hobby. Upgrade before the first real sale | Open |

## Decision log

| Date | Decision | Why | Ref |
|---|---|---|---|
| 2026-10-04 | Two Flask apps + shared `core` Python package, one Postgres DB | Matches the product idea. Logic isn't duplicated | architecture §1, A1 |
| 2026-10-04 | PostgreSQL over SQLite | Two concurrent writer servers, row locks, CHECK, triggers | A2 |
| 2026-10-04 | React + Vite + TypeScript + Tailwind for both frontends | Owner knows React. TS for safety | architecture §2 |
| 2026-10-04 | Server computes all prices. Browser sends code + qty only | Prevents price tampering | BR-5 |
| 2026-10-04 | "Discount" = switch whole order from MP to SP | Matches the owner's description | BR-4 |
| 2026-10-04 | Rejected carts saved as `orders.status='rejected'` | Traceability | project-overview §7 |
| ~~2026-10-04~~ | ~~Separate JWT secret + `aud` claim per server~~ (superseded by the Clerk + `azp` decision below) | | |
| 2026-10-04 | Ports 5001/5002 (APIs), 5173/5174 (web) in local dev | Avoid port 5000 conflicts | architecture §11 |
| ~~2026-10-04~~ | ~~Dev DB = native PostgreSQL 18~~ (superseded: Neon. Local PG 18 is now for tests only) | | |
| 2026-10-04 | Backend uses Python 3.12 via `py -3.12` (machine also has 3.10) | Spec requires 3.11+ | SETUP_GUIDE §4.1 |
| 2026-10-04 | One root `.env` shared by both servers locally. Per-server names for CORS and authorized parties | Simple config, clear separation | SETUP_GUIDE §7 |
| 2026-10-04 | **Managed cloud stack**: Neon (DB), Clerk (auth), Cloudinary (images), GitHub Actions (CI + migrations + backups). Hosting: see the Vercel decision below | Owner wants free, easy deployment | architecture A4, A7–A11 |
| 2026-10-04 | **Clerk** replaces self-built auth. Role in `public_metadata.role` as a session claim. Each API checks `azp` + role. Local `users` mirror (JIT + webhooks) | Less security code. Login UI and bot protection included | spec 02 |
| 2026-10-04 | **Neon** branches: `main` = prod, `dev` = development. Pooled URL for apps, direct URL for migrations/backups. Tests on local PG / CI service container | Serverless-friendly. Fast tests | architecture §9 |
| 2026-10-04 | **Cloudinary** for product images (no local `media/`) | Serverless has no disk. Free CDN + thumbnails | spec 03 |
| ~~2026-10-04~~ | ~~Render (APIs) + Cloudflare Pages (SPAs)~~ (superseded the same day by Vercel) | | |
| 2026-10-04 | **Vercel for everything**: 4 projects (admin-web, pos-web, admin-api, pos-api). Both APIs deploy `backend/`, with `SHOPDESK_SERVER` selecting the app. Functions in `sin1` | Owner's choice. One platform. Seconds-level cold starts | A9, A12, spec 10 |
| 2026-10-04 | Migrations run from GitHub Actions after CI passes. All migrations backward-compatible (expand → contract) | Vercel has no start command. Code and schema deploy independently | A13 |
| 2026-10-04 | Upload limit 4 MB + browser-side resize | Vercel function body limit ~4.5 MB | spec 03 |
| 2026-10-04 | Tests use a separate Neon database `shopdesk_test` (direct host). Local Postgres is optional | Owner chose the zero-password setup | SETUP_GUIDE §5 |
| 2026-10-04 | Frontend: React 19, Vite 8, Tailwind v4 (shared `theme.css`), TypeScript 6.0, ESLint 9 | TS 7 / ESLint 10 aren't supported by typescript-eslint / jsx-a11y yet | architecture §2 |
| 2026-10-04 | Flask-SQLAlchemy + Flask-Migrate. Alembic `env.py` always uses the direct URL (NullPool) | Matches the `flask db` commands in the docs. Neon-safe migrations | spec 01 |
| 2026-10-04 | JIT user mirror is created from the verified token claims (no Clerk API call per first request) | Faster serverless requests. Webhooks add the email | spec 02 §7.2 |
| 2026-10-04 | Audit table + trigger built in spec 02 (needed for user management), not spec 05 | Avoids a throwaway stub | spec 05 |
| 2026-10-04 | Upstash Redis for production rate limits | Serverless instances don't share memory | spec 09 |
| 2026-10-04 | Clerk: Access mode **Invite-only** (renamed from "Restricted"). Session claim `"metadata": "{{user.public_metadata}}"`, with the role read from `metadata.role` (Clerk's documented RBAC pattern) | Matches the current Clerk dashboard and docs | spec 02 §5, SETUP_GUIDE §3.3 |

## Known issues / backlog

| # | Item | Priority |
|---|---|---|
| B1 | Returns/refunds flow (reverse an order, restore stock) | Medium, post-v1 |
| B2 | GST invoices | Low, post-v1 |
| B3 | Fuzzy product search (pg_trgm) | Low |
| B4 | Offline mode for POS if the network drops | Low |
| B5 | ~~Move media to object storage~~ (done by design: Cloudinary) | — |
| B7 | Verify spec 01 criterion: health check works after 10+ min Neon idle (pre-ping) | Low, check during spec 02 |
| B6 | Staging environment (git `staging` branch + Neon `staging` branch + scoped Preview env + Clerk allowed origin) | Post-v1 |

## Session log

| Date | Who | What was done | Next |
|---|---|---|---|
| 2026-10-04 | Claude + owner | Created the `context/` docs: overview, architecture, UI, standards, AI rules, specs 01–10 | Start spec 01 |
| 2026-10-04 | Claude + owner | Wrote `SETUP_GUIDE.md` + `.env.example`. Checked the machine: Python 3.12 needs installing, and Postgres 18 is already running | Owner: finish the SETUP_GUIDE checklist, then start spec 01 |
| 2026-10-04 | Claude + owner | Switched to the free cloud stack (Neon, Clerk, Cloudinary, Render, Cloudflare Pages). Rewrote architecture, specs 01/02/09/10, SETUP_GUIDE and `.env.example`. Updated specs 03/05/06, standards and AI rules | Owner: create the accounts + fill `.env` (SETUP_GUIDE §3, §7), then start spec 01 |
| 2026-10-04 | Claude + owner | Added `.gitignore` (secrets, venv, node_modules, dumps, caches), ran `git init -b main`, added remote `origin` → github.com/HiteshPatil2610/shopdesk. Checked that `.env` is ignored. Nothing committed yet | First commit + push (owner's go-ahead), then spec 01 |
| 2026-10-04 | Claude + owner | Switched hosting from Render + Cloudflare Pages to **Vercel** (4 projects). Updated architecture (§1–3, 9–13, ADRs A9/A12/A13), rewrote spec 10, and updated specs 01/03/09, SETUP_GUIDE, `.env.example`, CLAUDE.md, standards, README and overview | Same as above. Owner: set `MAX_UPLOAD_MB=4` in local `.env` |
| 2026-10-04 | Claude | **Spec 01 built**: `backend/` (core config/db/errors/money/health, admin_api + pos_api factories, Vercel entry, Alembic baseline applied to Neon dev), `frontend/` (npm workspaces: shared pkg + admin-web + pos-web, Tailwind v4, Vitest), CI workflow, pre-commit, dev.ps1, README. Created Neon DB `shopdesk_test` + set TEST_DATABASE_URL. All checks green locally | Spec 02 (Clerk auth) |
| 2026-10-04 | Claude | **Spec 02 built**: users/webhook/audit tables (migration 0002, applied to Neon dev), Clerk JWT verification with `azp` + role checks, JIT mirror, user management via Clerk SDK, signed webhooks, `promote-admin` CLI, default-deny route test. Frontend: Clerk sign-in, AuthGate + wrong-app screen, admin layout + Users page, POS shell + pre-warm. CI actions bumped to v7 | Owner: sign in as `owner` on both apps (SETUP_GUIDE §9.3). Then specs 03 + 04 |
| 2026-10-04 | Claude + owner | Fixed setup issues found in the manual test: partial CLERK_JWT_KEY (now validated at startup + `setup_tools fetch-clerk-key`), empty owner metadata (promote-admin), top-level `role` claim now accepted. Fixed modal focus-jump bug. Owner confirmed everything works | Specs 03 + 04 |
