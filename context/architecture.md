# Architecture — ShopDesk

> **Platform:** managed cloud services. **Vercel** (both React apps + both Flask APIs as Python serverless functions), **Neon** (Postgres), **Clerk** (auth), **Cloudinary** (images), **GitHub** (code, CI, migrations, backups). Costs: a domain name (Clerk production mode needs one). Vercel's free **Hobby** plan is for non-commercial use only, so running the real shop on it needs **Vercel Pro** (see §12).

## 1. High-level design

```
   Owner / Manager browser                         Cashier browser
            │                                             │
            ▼                                             ▼
┌──────────────────────────┐                ┌──────────────────────────┐
│ admin-web (React SPA)    │                │ pos-web (React SPA)      │
│ Vercel (static)          │                │ Vercel (static)          │
│ admin.<domain>           │                │ pos.<domain>             │
└───────┬───────────┬──────┘                └──────┬───────────┬───────┘
        │ sign-in   │ /api/*  Authorization: Bearer <Clerk session JWT>
        ▼           │                              │           ▼ sign-in
   ┌─────────────────────────── Clerk (auth) ───────────────────────────┐
   │ users · passwords · sessions · roles in public_metadata · webhooks │
   └────────────────────────────────────────────────────────────────────┘
                    ▼                              ▼
┌──────────────────────────┐                ┌──────────────────────────┐
│ admin_api (Flask)        │                │ pos_api (Flask)          │
│ SERVER 1 · Vercel fn     │                │ SERVER 2 · Vercel fn     │
│ admin-api.<domain>       │                │ pos-api.<domain>         │
│ products, pricing, stock,│                │ product lookup, cart     │
│ users, audit, reports,   │                │ quote, confirm/reject,   │
│ image upload, webhooks   │                │ receipt                  │
└──────┬─────────────┬─────┘                └────────────┬─────────────┘
       │ both import backend/core (models · services ·   │
       │ pricing · audit · auth · db)                    │
       │             ▼                                   │
       │   ┌────────────────────┐                        │
       │   │ Cloudinary         │◄── image URLs (CDN) ── browsers
       │   │ product images     │
       │   └────────────────────┘
       └──────────────────┬──────────────────────────────┘
                          ▼
            ┌──────────────────────────────┐
            │ Neon Postgres (serverless)   │
            │ branch main → production     │
            │ branch dev  → development    │
            └──────────────────────────────┘
```

**Key idea (unchanged):** two separate Flask applications that both import one shared Python package, `core`. All business rules live in `core`. Each server registers **only** the routes it needs. The POS server has no product-edit, user or audit endpoints at all.

**On Vercel**, "two servers" means **two separate Vercel projects** (`shopdesk-admin-api`, `shopdesk-pos-api`). Each has its own domain, its own environment variables and secrets, and its own logs. Both projects deploy the same `backend/` folder, and the env var `SHOPDESK_SERVER=admin|pos` picks which Flask app the entry point builds (§3, ADR A12). A request to the POS project can never reach an admin route, because that app doesn't register them.

**What moved to managed services:** passwords, login screens, sessions and brute-force protection → **Clerk**. Image storage, resizing and CDN → **Cloudinary**. Database hosting, backups/point-in-time restore and branching → **Neon**.

## 2. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language (backend) | Python 3.12 | Your main language |
| Web framework | Flask 3.x (app factory + blueprints) | Familiar. Two apps share code easily |
| ORM | SQLAlchemy 2.x (typed `Mapped[]`) | Row locking (`with_for_update`), mature |
| DB driver | psycopg 3 (`psycopg[binary]`) | Works with Neon's pooler |
| Migrations | Alembic via Flask-Migrate | **Run only from admin_api**, over Neon's **direct** (unpooled) connection |
| Validation | Pydantic v2 | Request/response schemas |
| **Auth** | **Clerk.** Frontend: `@clerk/react` (v6+). Backend: JWT verified with PyJWT + Clerk's public key. User management via `clerk-backend-api` | Login UI, sessions, password security and bot protection are handled for us |
| Webhooks | Clerk → `svix` signature verification | Keeps the local `users` mirror in sync and audits sign-ins |
| Rate limiting | Flask-Limiter. Dev uses memory storage. Production uses **Upstash Redis** (free tier, via the Vercel Marketplace) | Serverless instances don't share memory, so limits need a shared store |
| CORS | Flask-CORS, explicit origins | Frontends and APIs are on different subdomains |
| **Images** | **Cloudinary** (`cloudinary` Python SDK) + Pillow for validation | Free CDN, on-the-fly thumbnails, nothing needs a disk (serverless functions have none) |
| **Database** | **Neon Postgres** (free tier) | Postgres features we rely on: `FOR UPDATE`, CHECK, JSONB, triggers. Serverless, with branches for dev/prod |
| Frontend | React 19 + Vite 8 + TypeScript 6 (ESLint 9; typescript-eslint doesn't support TS 7 yet) | |
| Styling | Tailwind CSS | |
| Data fetching | TanStack Query + Axios (token from `useAuth().getToken()`) | |
| Forms | React Hook Form + Zod | |
| Routing | React Router (latest major, library mode), added in spec 02 | |
| Charts | Chart.js (react-chartjs-2) | |
| Tests | pytest (+ local Postgres or a Neon test branch), Vitest, RTL, Playwright later | |
| Lint/format | ruff + black, ESLint + Prettier | |
| **Hosting** | **Vercel**: 4 projects from one repo. 2 static Vite sites + 2 Python serverless (Flask, WSGI) projects, functions in region `sin1` (Singapore, next to Neon) | Git deploys, preview URLs, free custom domains + HTTPS, cold starts in seconds rather than the ~1 min of sleeping containers |
| CI / migrations / backups | GitHub Actions | Tests on push, `flask db upgrade` on Neon `main` after tests pass, nightly `pg_dump` |

## 3. Repository layout

```
ShopDesk/
├── CLAUDE.md
├── README.md
├── SETUP_GUIDE.md                # accounts, keys, .env, first run
├── context/                      # ← these docs
├── .env.example                  # backend env template (root .env used in dev)
├── .github/workflows/
│   ├── ci.yml                    # lint + tests on push/PR
│   ├── migrate.yml               # after CI passes on main: flask db upgrade on Neon main
│   └── backup.yml                # nightly pg_dump of Neon
│
├── backend/                      # Root Directory of BOTH Vercel API projects
│   ├── vercel.json               # rewrites everything → api/index.py, region sin1
│   ├── api/
│   │   └── index.py              # entry: SHOPDESK_SERVER=admin → admin_api, =pos → pos_api
│   ├── pyproject.toml
│   ├── requirements.txt / requirements-dev.txt   # Vercel installs requirements.txt
│   ├── core/                     # ★ shared package: imported by BOTH servers
│   │   ├── config.py             # Settings from env (pydantic-settings)
│   │   ├── db.py                 # engine (Neon-aware), session, Base
│   │   ├── models/               # user, product, pricing, order, stock, audit
│   │   ├── schemas/              # Pydantic
│   │   ├── services/             # ★ business logic + transactions
│   │   │   ├── auth_service.py   # resolve Clerk user → local user, role checks
│   │   │   ├── user_service.py   # create/update users via Clerk Backend API + mirror
│   │   │   ├── product_service.py  pricing_service.py  stock_service.py
│   │   │   ├── order_service.py    audit_service.py    report_service.py
│   │   ├── clerk_auth.py         # verify Clerk JWT (PyJWT, public key, azp)
│   │   ├── pricing.py            # ★ pure pricing formula
│   │   ├── money.py              # Decimal helpers
│   │   ├── security.py           # require_role decorator, ActorContext
│   │   ├── media.py              # validate (Pillow) + upload/delete (Cloudinary) + URL builder
│   │   ├── errors.py
│   │   └── cli.py                # promote-admin, seed, etc.
│   ├── admin_api/                # ★ SERVER 1
│   │   ├── __init__.py  wsgi.py
│   │   └── routes/ auth.py products.py pricing.py stock.py orders.py audit.py
│   │               users.py reports.py webhooks.py
│   ├── pos_api/                  # ★ SERVER 2
│   │   ├── __init__.py  wsgi.py
│   │   └── routes/ auth.py products.py cart.py orders.py
│   ├── migrations/
│   └── tests/ unit/ services/ api/
│
└── frontend/
    ├── packages/shared/          # api client (Clerk token), formatINR, types, UI atoms, Tailwind v4 theme.css
    ├── admin-web/                # ★ React app for Server 1   (vercel.json: SPA rewrite + security headers)
    └── pos-web/                  # ★ React app for Server 2   (vercel.json: SPA rewrite + security headers)
```

Frontend uses **npm workspaces**. There is no local `media/` folder: images live in Cloudinary.

**`backend/api/index.py`** (the only Vercel-specific Python file):
```python
import os
from core.config import settings  # validates env on cold start

if os.environ.get("SHOPDESK_SERVER") == "admin":
    from admin_api import create_app
elif os.environ.get("SHOPDESK_SERVER") == "pos":
    from pos_api import create_app
else:
    raise RuntimeError("SHOPDESK_SERVER must be 'admin' or 'pos'")

app = create_app()   # Vercel's Python runtime serves this WSGI app
```
**`backend/vercel.json`**:
```json
{
  "regions": ["sin1"],
  "rewrites": [{ "source": "/(.*)", "destination": "/api/index" }]
}
```
Local development doesn't use either file. `flask --app admin_api run` still works as before.

## 4. Backend layering (strict)

```
routes (blueprints)  →  schemas (validate)  →  services  →  models / db
      thin                Pydantic               business      SQLAlchemy
```

| Layer | May do | Must NOT do |
|---|---|---|
| **routes** | Parse request, validate, `@require_role`, call **one** service, return JSON | Business logic, direct DB queries, commit |
| **services** | Business rules, transactions, `audit_service.record()`, row locks, calls to Clerk/Cloudinary SDKs | Read `flask.request` directly (use `ActorContext`). Keep state in memory between requests (serverless instances come and go) |
| **pricing.py / money.py** | Pure Decimal functions | DB, Flask, network |
| **models** | Columns, relationships, constraints | Business logic |

```python
@dataclass(frozen=True)
class ActorContext:
    user_id: int | None          # local users.id
    clerk_user_id: str | None
    username: str
    role: str
    source: Literal["admin", "pos", "system"]
    ip: str | None
    user_agent: str | None
```

## 5. Database schema

All tables have `id BIGSERIAL PK`. Timestamps are `TIMESTAMPTZ` in UTC, shown in IST.

### 5.1 `users` (local mirror of Clerk users)
Clerk owns identity and passwords. ShopDesk keeps a mirror so orders, products and audit rows can reference a user by foreign key and still show their name if the Clerk account is deleted.

| Column | Type | Notes |
|---|---|---|
| clerk_user_id | VARCHAR(64) UNIQUE NOT NULL | `user_2abc…` |
| username | VARCHAR(50) NULL | from Clerk (cashiers may sign in with a username) |
| email | VARCHAR(255) NULL | from Clerk |
| full_name | VARCHAR(120) NOT NULL | |
| role | VARCHAR(20) NOT NULL | `admin` \| `manager` \| `cashier` (CHECK). Mirrors Clerk `public_metadata.role` |
| is_active | BOOLEAN NOT NULL DEFAULT true | false when banned/deleted in Clerk |
| last_seen_at | TIMESTAMPTZ NULL | updated at most once per minute |
| created_at, updated_at | TIMESTAMPTZ | |

There are no password, lockout or token columns. Clerk handles all of that.

### 5.2 `categories`
`name VARCHAR(80) UNIQUE NOT NULL`, `is_active BOOLEAN DEFAULT true`.

### 5.3 `products`
| Column | Type | Notes |
|---|---|---|
| code | VARCHAR(20) UNIQUE NOT NULL | `P00001` from sequence |
| barcode | VARCHAR(64) UNIQUE NULL | |
| name | VARCHAR(150) NOT NULL | |
| description | TEXT NULL | |
| category_id | FK → categories NULL | |
| unit | VARCHAR(10) NOT NULL DEFAULT 'pcs' | |
| image_public_id | VARCHAR(255) NULL | Cloudinary public ID, e.g. `shopdesk/products/3f2a…` |
| cost_price | NUMERIC(12,2) NOT NULL | CHECK ≥ 0 |
| market_price | NUMERIC(12,2) NOT NULL | |
| selling_price | NUMERIC(12,2) NOT NULL | |
| mp_is_manual, sp_is_manual | BOOLEAN NOT NULL DEFAULT false | |
| quantity | INT NOT NULL DEFAULT 0 | **CHECK (quantity >= 0)** |
| reorder_level | INT NOT NULL DEFAULT 5 | |
| is_active | BOOLEAN NOT NULL DEFAULT true | |
| version | INT NOT NULL DEFAULT 1 | optimistic locking |
| created_by, updated_by | FK → users | |
| created_at, updated_at | TIMESTAMPTZ | |

Constraint `CHECK (cost_price <= selling_price AND selling_price <= market_price)`. Indexes: code, barcode, lower(name), is_active.

### 5.4 `pricing_settings` (single row, id = 1)
`markup_low_pct NUMERIC(6,2)=95`, `markup_high_pct NUMERIC(6,2)=90`, `markup_threshold NUMERIC(12,2)=500`; `small_mp_limit=500`, `small_mp_step=10`, `small_mp_alt_step=50`, `mp_step=50`, `mp_alt_step=100`; `sp_discount_pct=10`, `sp_step=10`, `sp_avoid_ten BOOLEAN NOT NULL DEFAULT true`; `updated_by`, `updated_at`. Money limits use `NUMERIC(12,2)`, rounding steps `NUMERIC(8,2)` and percentages `NUMERIC(6,2)`.

MP rounds upward with a primary/alternate choice stored on the product. At/above the cost threshold, raw MP is at least `markup_threshold × (1 + markup_low_pct/100)` to prevent a price drop. SP rounds down, then optionally changes a tens digit of 1 to 0 for values ≥ ₹100 (1212 → 1200; 1293 → 1290), with the cost ≤ SP ≤ MP constraint taking priority. Migration 0003 creates the settings; additive migration 0004 adds the switch. Saving settings does not reprice existing products until explicit apply.

### 5.5 `orders`
Audit viewing uses `core/services/audit_view_service.py` behind read-only admin routes. Admins/managers can query and view details; only admins export. CSV streams up to 100,000 rows with formula-neutralized cells and a UTF-8 BOM, appending an export event in the service before streaming. The existing append-only table and trigger remain unchanged. Product history is scoped by entity type/id; orders follow spec 07.

| Column | Type | Notes |
|---|---|---|
| order_number | VARCHAR(30) UNIQUE NOT NULL | `INV-20261004-0007` / `REJ-…` |
| status | VARCHAR(15) NOT NULL | `confirmed` \| `rejected` |
| customer_name | VARCHAR(120) NOT NULL | |
| customer_phone | VARCHAR(20) NULL | |
| cashier_id | FK → users NOT NULL | |
| discount_applied | BOOLEAN NOT NULL | |
| payment_mode | VARCHAR(10) NULL | `cash` \| `upi` \| `card` |
| item_count | INT NOT NULL | |
| subtotal_mp, discount_amount, total_amount, total_cost | NUMERIC(12,2) | total_cost never sent to POS |
| reject_reason | VARCHAR(255) NULL | |
| idempotency_key | UUID UNIQUE NOT NULL | |
| created_at | TIMESTAMPTZ | |

### 5.6 `order_items`
`order_id`, `product_id`, snapshots `product_code`, `product_name`, `quantity INT CHECK > 0`, `unit_cost`, `unit_mp`, `unit_sp`, `unit_price_charged`, `line_total` (all NUMERIC(12,2)).

### 5.7 `stock_movements` (ledger)
`product_id`, `change INT (≠0)`, `quantity_after INT`, `reason` (`initial|restock|sale|adjustment|damage|correction`), `reference_type`, `reference_id`, `note`, `user_id`, `created_at`.
Invariant: `products.quantity == SUM(stock_movements.change)`.

### 5.8 `audit_logs` (append-only)
`occurred_at`, `actor_user_id`, `actor_username`, `source` (`admin|pos|system`), `action`, `entity_type`, `entity_id`, `summary`, `changes JSONB`, `metadata JSONB`, `ip_address INET`, `user_agent`.
Indexes: `occurred_at DESC`, `(entity_type, entity_id)`, `actor_user_id`, `action`. **Trigger blocks UPDATE/DELETE.**

### 5.9 `daily_counters`
`(counter_date DATE, kind VARCHAR(10), last_value INT, PK(counter_date, kind))`, where kind is `INV` or `REJ`.

### 5.10 `webhook_events`
`svix_id VARCHAR(64) UNIQUE`, `type`, `received_at`. Used to ignore duplicate Clerk webhook deliveries (idempotency).

### 5.11 ER summary
```
users 1─* products(created_by/updated_by), orders(cashier_id), stock_movements, audit_logs
categories 1─* products
products 1─* order_items *─1 orders
products 1─* stock_movements
```

## 6. Critical flows

### 6.1 Request authentication (both servers)
```
browser: token = await clerk.getToken()          # short-lived (~60s) session JWT, auto-refreshed
         axios → Authorization: Bearer <token>

server:  clerk_auth.verify(token):
           RS256 signature with CLERK_JWT_KEY (no network call)
           exp / nbf (5s leeway)
           azp ∈ <THIS_SERVER>_AUTHORIZED_PARTIES   # admin_api only accepts tokens minted for admin-web
         claims.metadata.role (custom session claim "metadata": "{{user.public_metadata}}")
         auth_service.resolve_user(claims): find users by clerk_user_id;
           if missing → fetch from Clerk Backend API and insert (just-in-time sync)
           if not is_active → 401
         @require_role(...) checks the role → 403 if not allowed
         → ActorContext
```

### 6.2 Add product (Admin)
```
POST /api/products (multipart)
  product_service.create(data, image, actor):
     public_id = media.upload_product_image(file)    # Pillow-validate → re-encode WebP → Cloudinary
     BEGIN
       compute MP/SP (pricing.py) unless manual · validate BR-2 · next code
       INSERT product · initial stock_movement · audit 'product.create'
     COMMIT
     on failure → media.delete(public_id)            # compensating action
```

### 6.3 Billing: quote (POS, read-only)
`POST /api/cart/quote {items:[{code,qty}], discount_applied}` → server prices, no writes.

Implemented in `core/services/order_service.py` with explicit cost-free quote schemas.
One query loads products, duplicate codes merge, and quantities above 10,000 after merging
are rejected. Unknown/inactive/short-stock lines block confirmation. Browser prices are ignored.
The POS reducer persists code/qty, customer fields and display metadata in `sd_pos_cart`;
prices and quotes remain in TanStack Query. Quotes debounce 150ms, consume its AbortSignal,
and hide totals until the current request finishes. Draft review/clear are available;
payment, saved rejection and confirmation belong to §6.4 and spec 07.

### 6.4 Billing: confirm (POS) — the most important transaction
```
POST /api/orders/confirm {idempotency_key, customer_name, customer_phone?, payment_mode?,
                          discount_applied, items:[{code, qty}]}
  existing order for idempotency_key → return it (200)
  BEGIN                                               # one transaction (works with Neon's pooler)
    SELECT … FROM products WHERE code IN (…) AND is_active ORDER BY id FOR UPDATE
    check stock for every line → 409 INSUFFICIENT_STOCK (rollback) if any short
    prices from locked rows · next invoice number
    INSERT order + items (snapshots) · UPDATE quantity · INSERT stock_movements
    audit 'order.confirm'
  COMMIT → 201
```

### 6.5 Reject
Saves `orders(status='rejected')` with snapshots. **No stock change.** Audit `order.reject`.

### 6.6 Edit product (optimistic locking)
`UPDATE … WHERE id=:id AND version=:v` → 0 rows → 409 VERSION_CONFLICT.

### 6.7 Clerk webhook (admin_api)
```
POST /api/webhooks/clerk     (public, but svix-signed)
  verify svix signature with CLERK_WEBHOOK_SIGNING_SECRET → else 400
  dedupe by svix-id (webhook_events)
  user.created / user.updated → upsert users mirror (role, name, is_active)
  user.deleted                → is_active = false (row kept for history)
  session.created             → audit 'auth.login'
  session.ended / removed / revoked → audit 'auth.logout'
```
Webhooks are a convenience, not a requirement. Just-in-time sync (6.1) keeps things working locally where Clerk can't reach your machine.

## 7. API surface

JSON over HTTPS. Base path `/api`. Error shape: `{ "error": { "code", "message", "details" } }`.

### 7.1 Admin API (Server 1)
| Method | Path | Role |
|---|---|---|
| GET | /api/health | public |
| GET | /api/auth/me | mgr+ |
| POST | /api/webhooks/clerk | svix signature |
| GET/POST | /api/products | mgr+ |
| GET/PATCH | /api/products/{id} | mgr+ |
| POST/DELETE | /api/products/{id}/image | mgr+ |
| POST | /api/products/{id}/deactivate · /activate · /recalculate-prices | mgr+ |
| POST | /api/pricing/preview | mgr+ |
| GET/PUT | /api/pricing/settings | GET mgr+, PUT admin |
| POST | /api/pricing/apply | admin |
| GET/POST | /api/categories | mgr+ |
| POST | /api/stock/{product_id}/adjust | mgr+ |
| GET | /api/stock/{product_id}/movements | mgr+ |
| GET | /api/stock/verify | admin |
| GET | /api/orders · /api/orders/{id} | mgr+ |
| GET | /api/audit-logs · /{id} | mgr+ |
| GET | /api/audit-logs/export.csv | admin |
| GET | /api/reports/* | mgr+ |
| GET/POST/PATCH | /api/users, /api/users/{id} | admin |
| POST | /api/users/{id}/reset-password · /ban · /unban · /revoke-sessions | admin |

### 7.2 POS API (Server 2)
| Method | Path | Role |
|---|---|---|
| GET | /api/health | public |
| GET | /api/auth/me | cashier+ |
| GET | /api/products?search=&page= (no cost fields) | cashier+ |
| GET | /api/products/lookup?code= | cashier+ |
| POST | /api/cart/quote | cashier+ |
| POST | /api/orders/confirm · /reject | cashier+ |
| GET | /api/orders/{order_number}/receipt | cashier+ (own) / mgr+ |
| GET | /api/orders/mine?date=today | cashier+ |

Image URLs in responses point straight at Cloudinary's CDN (`https://res.cloudinary.com/<cloud>/image/upload/c_fill,w_256,h_256,f_auto,q_auto/<public_id>`).

## 8. Auth design (summary; full detail in spec 02)

- **One Clerk application** serves both frontends (same user pool). There's a *development* instance for local work and a *production* instance (which needs your own domain).
- **Public sign-up disabled** (Clerk **Access mode = Invite-only**). The admin creates staff from the ShopDesk Users page, which calls the Clerk Backend API, or in the Clerk dashboard.
- **Role** lives in Clerk `public_metadata.role`. It's copied into the session token via the custom claim `"metadata": "{{user.public_metadata}}"`, read as `metadata.role`, and mirrored into `users.role`.
- **Server separation:** each API only accepts tokens whose `azp` (authorized party) is its own frontend's origin, **and** checks the role. A cashier can't use the admin API even with a valid Clerk session.
- Tokens are short-lived (~60 s) and refreshed by the Clerk SDK. Banning a user in Clerk cuts them off within about a minute, and the local `is_active` mirror cuts them off straight away once the webhook or the next sync arrives.
- Tokens are sent as `Authorization: Bearer` (not cookies), so there's no CSRF exposure. CORS allows only the two frontend origins.

## 9. Neon specifics

| Topic | Rule |
|---|---|
| Connection strings | `DATABASE_URL` = **pooled** (host contains `-pooler`) for the running apps. `DATABASE_URL_UNPOOLED` = **direct** for Alembic migrations and `pg_dump` |
| SSL | Always `sslmode=require` (Neon's strings include it) |
| Pooler compatibility | Neon's pooler runs PgBouncer in transaction mode. Pass `connect_args={"prepare_threshold": None}` to psycopg. Never rely on session state (`SET`, temp tables, advisory locks outside a transaction). `SELECT … FOR UPDATE` inside a transaction is fine |
| Scale to zero | Compute suspends after ~5 min idle. Use `pool_pre_ping=True`, `pool_recycle=300` |
| Serverless pool size | Each Vercel instance keeps its own small pool: `pool_size=2`, `max_overflow=3`. Neon's pooler absorbs many instances. Never use the direct URL from functions |
| URL prefix | Neon and the Vercel–Neon integration hand out `postgresql://`. `core/config.py` rewrites `postgres://` / `postgresql://` → `postgresql+psycopg://` automatically |
| Branches | `main` = production, `dev` = development (reset from `main` when you want fresh data). Tests use a **separate database `shopdesk_test`** in the same Neon project (direct host), which pytest wipes and rebuilds each run. A local Postgres `shopdesk_test` also works |
| Region | Neon in Singapore (`aws-ap-southeast-1`) and Vercel functions in `sin1` (Singapore). Being in the same region keeps the confirm transaction fast |
| Storage | Free tier ≈ 0.5 GB per project, plenty for text data. Images are in Cloudinary, not the DB |

## 10. Configuration

Spec 09 adds `core/hardening.py`: separate shared write (120/min), quote (300/min),
CSV (5/min) and webhook (60/min) buckets, keyed by verified Clerk subject or direct IP.
Production uses TLS Redis without a memory fallback. API responses receive no-store,
nosniff, frame denial and a JSON-only CSP; production adds HSTS. Runtime production
configuration requires exact HTTPS origins, `shopdesk_app` with TLS, live Clerk keys
and Redis. Web CSP is generated for exact deployment hosts; production builds reject
test keys or CSP mismatches. `MANUAL_DEPLOYMENT.md` describes manual deployment and
restricted DB roles. Backups require a private repository; migration workflows reapply
grants after successful migrations. These scripts do not establish production readiness
until the owner completes the production permission/header/backup/restore checks.

The backend reads env vars, from the root `.env` in development or each Vercel API project's *Environment Variables* in production. The frontends read `VITE_*` vars at build time (each Vercel frontend project's settings in production). **Full list: [SETUP_GUIDE.md §7–8](../SETUP_GUIDE.md).** Key ones:

| Var | Used by |
|---|---|
| DATABASE_URL, DATABASE_URL_UNPOOLED, TEST_DATABASE_URL | backend / migrations / pytest |
| CLERK_SECRET_KEY, CLERK_JWT_KEY, CLERK_WEBHOOK_SIGNING_SECRET | backend |
| ADMIN_AUTHORIZED_PARTIES, POS_AUTHORIZED_PARTIES | admin_api / pos_api |
| ADMIN_CORS_ORIGINS, POS_CORS_ORIGINS | admin_api / pos_api |
| CLOUDINARY_URL, CLOUDINARY_FOLDER | backend |
| SHOPDESK_SERVER (`admin` / `pos`) | Vercel API projects only |
| RATELIMIT_STORAGE_URI (Upstash `rediss://…` in prod) | backend |
| VITE_CLERK_PUBLISHABLE_KEY, VITE_API_BASE_URL | frontends |

When you add a variable, add it to `.env.example`, `core/config.py` and SETUP_GUIDE in the same change.

## 11. Environments and ports

| | Local development | Production |
|---|---|---|
| admin-web | http://localhost:5173 (Vite, proxies `/api` → :5001) | https://admin.\<domain\> (Vercel project `shopdesk-admin-web`) |
| pos-web | http://localhost:5174 (Vite, proxies `/api` → :5002) | https://pos.\<domain\> (Vercel project `shopdesk-pos-web`) |
| admin_api | http://localhost:5001 | https://admin-api.\<domain\> (Vercel project `shopdesk-admin-api`) |
| pos_api | http://localhost:5002 | https://pos-api.\<domain\> (Vercel project `shopdesk-pos-api`) |
| Database | Neon branch `dev` | Neon branch `main` |
| Clerk | Development instance (`pk_test_…`) | Production instance (`pk_live_…`) |
| Cloudinary folder | `shopdesk-dev/products` | `shopdesk/products` |
| Tests | Neon database `shopdesk_test` (or local Postgres) | GitHub Actions Postgres service |

## 12. Platform constraints (Vercel + free tiers) and how the design handles them

| Constraint | Effect | Mitigation |
|---|---|---|
| **Vercel Hobby (free) is for personal, non-commercial use only** | Running a real shop on Hobby breaks Vercel's terms | Build and test on Hobby. Before real sales, move the team to **Vercel Pro** (~$20/month per member, check pricing) |
| Functions are **serverless**: instances start and stop on demand | First request after idle has a **cold start of ~1–3 s** (Python + imports) | Keep imports lean at module level. pos-web sends one `/api/health` "pre-warm" request when the billing screen loads. No long-running state in memory |
| **Request body limit ~4.5 MB** per function call | Large image uploads would fail before reaching Flask | Browser resizes images to ≤ 1024 px WebP before uploading. Server limit `MAX_UPLOAD_MB=4` (spec 03) |
| No persistent disk | Uploaded files would vanish | Images go to Cloudinary |
| Memory isn't shared between instances | In-memory rate limits don't work | Upstash Redis (free) as the Flask-Limiter store in production |
| No "start command" to run migrations | Schema changes need another trigger | GitHub Actions `migrate.yml` runs `flask db upgrade` on Neon `main` after CI passes. **Migrations must be backward-compatible** (expand → deploy → contract), because Vercel may deploy the code before or after the migration finishes |
| Function max duration / runtime log retention are limited on Hobby | Long jobs fail. Logs disappear quickly | All requests are short (< 2 s). The **audit log in Postgres** is the permanent record, not Vercel logs |
| Neon compute scales to zero | ~sub-second wake on first query | `pool_pre_ping`, small pool |
| Clerk production instance needs a custom domain | Can't use `*.vercel.app` for production sign-in | Buy a cheap domain and attach subdomains to the 4 Vercel projects |
| Limits change over time | — | Check each pricing page before go-live (SETUP_GUIDE §2) |

## 13. Architecture decisions (ADR summary)

| # | Decision | Alternatives | Reason |
|---|---|---|---|
| A1 | Two Flask apps + shared `core` | One app | Product requirement. Smaller attack surface at the counter |
| A2 | Postgres (Neon) | SQLite, MySQL | Concurrent writers, `FOR UPDATE`, CHECK, JSONB, triggers |
| A3 | Server-computed prices | Client totals | Security (BR-5) |
| A4 | **Clerk** for identity, local `users` mirror for FKs/audit | Self-built JWT auth | Less security-critical code to write. Login UI and bot protection included. Free tier covers a shop |
| A5 | Pessimistic lock on sale, optimistic on admin edit | Lock-free | Never oversell |
| A6 | Stored MP/SP + manual flags, snapshots on orders | Compute on the fly | Stable, editable prices and correct history |
| A7 | **Cloudinary** for images | Local disk, S3/R2, Vercel Blob | Serverless has no persistent disk. Cloudinary gives CDN + thumbnails for free |
| A8 | **Neon** pooled URL for apps, direct URL for migrations | Direct only | Serverless-friendly connection handling |
| A9 | **Vercel** for all 4 deployables (owner's choice, 2026-10-04) | Render + Cloudflare Pages (earlier plan), Cloud Run | One platform, git deploys, seconds-not-minutes cold starts. Trade-off: Hobby is non-commercial, so Pro is needed for the live shop |
| A10 | Bearer tokens (Clerk) instead of cookies | Cookie sessions | Cross-subdomain APIs with no CSRF to handle |
| A11 | `azp` + role checks per server | Separate Clerk apps | One user pool. Still a hard boundary between servers |
| A12 | Two Vercel API projects share Root Directory `backend/`. `SHOPDESK_SERVER` selects the app in `api/index.py` | One project with both apps, or separate root folders | Keeps the "two servers" separation (own domain, env, secrets, logs) without copying code, and `core/` stays inside the deployed folder |
| A13 | Migrations from GitHub Actions, backward-compatible only | Migrating in a start command / build step | Vercel has no start command. CI already holds the tests, and the migration should run only after they pass |
