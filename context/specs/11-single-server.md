# Spec 11 — Single Server (one app, one deployment)

**Status:** 🟨 Approved; implementation in progress. · **Depends on:** 01–09 (built) · **Replaces parts of:** spec 10 (deployment), architecture §1/§3/§7/§10/§11, ADRs A1, A9, A11, A12 · **Server(s):** both, merged

## 1. Goal
Run ShopDesk as **one Flask API and one React web app on one Vercel project and one domain**, instead of 2 APIs + 2 web apps on 4 projects and 4 domains. The product idea stays the same:
- the **Admin Console** (owner/manager) and the **Billing Counter** (cashier) stay two separate areas with their own screens;
- a cashier still can't see or use admin screens, admin data or cost prices;
- both areas share the same database, rules, audit log and stock ledger.

Only the **packaging** changes. Security moves from "two separate servers" to "two separate areas inside one server, each with a hard role check".

## 2. Why (owner decision, 2026-10-05)
| | Today (4 deployables) | After (1 deployable) |
|---|---|---|
| Vercel projects | 4 (`admin-web`, `pos-web`, `admin-api`, `pos-api`) | **1** (`shopdesk`) |
| Domains / DNS records | 4 subdomains + Clerk | **1** (`shop.<domain>` or the apex) + Clerk |
| Env var sets to maintain | 4 | **1** |
| Local dev processes | 4 (5001, 5002, 5173, 5174) | **2** (API 5001 + web 5173) |
| Cross-origin setup (CORS, `connect-src` to other hosts) | Needed | **Gone**: web and API share one origin |
| Cold starts | Each API goes cold on its own | One function, kept warm by both areas |
| Sign-in | One Clerk session, two apps to open | One sign-in, then the right area opens by role |

What we give up (accepted):
- **Admin code is deployed next to POS code.** Before, a cashier's token could not reach admin routes because those routes did not exist on the POS server *and* its `azp` was wrong. Now the admin routes exist on the same server, and the **role check** (plus tests that prove it) is what stops the cashier. This is how most well-built multi-role apps work.
- **One deploy updates both areas.** A broken release affects billing and admin together. Mitigation: CI must be green before deploy, and Vercel's *Instant Rollback* takes seconds.
- **No separate logs/secrets per server.** Not needed for one shop. Logs still show the area (`/api/admin/...` vs `/api/pos/...`).

## 3. Scope
**In:**
- Merge `admin_api` + `pos_api` into one Flask app with two **areas**: `/api/admin/*` and `/api/pos/*`.
- Make "area" (not "server") the unit for role ceilings, request-size limits, rate-limit buckets and audit `source`.
- Merge `admin-web` + `pos-web` into one React app `frontend/web` with two lazy-loaded areas: `/admin/*` and `/pos/*`.
- One Vercel project: static web build + one Python function, same domain.
- Update config/env vars, tests, CI, workflows, scripts, launch config and all docs.

**Out (explicitly not in this spec):**
- Any change to business logic in `core/services`, pricing, stock, orders, the audit trigger or the database schema. **No migration is needed.**
- New features (idle lock screen, kiosk mode, thermal printer). Listed in §12 as possible follow-ups.
- Actually deploying to production (still the owner's manual step, spec 10 / `MANUAL_DEPLOYMENT.md`).

## 4. Business rules touched
None of the BR-x rules change. These architecture rules are **re-worded**, not weakened:
| Rule | Before | After |
|---|---|---|
| AU-5 (who may use which server) | `SERVER_ROLES["admin"] = {admin, manager}`, `["pos"] = {admin, manager, cashier}` | Same sets, keyed by **area**: `AREA_ROLES["admin"]`, `AREA_ROLES["pos"]` |
| BR-12 (no cost/profit in POS responses) | Enforced by the POS serializers + test | Unchanged: every `/api/pos/*` route uses the POS serializers; the "no cost in POS" test runs over **all** `/api/pos/*` routes |
| A11 (`azp` + role per server) | Each API accepts only its own frontend's `azp` | One frontend, so `azp` must equal the one app origin. The role ceiling per area replaces the "other app's token" protection |
| Default deny | Every route has `@require_role` or `@public` | Unchanged, plus: every route must live under `/api/admin`, `/api/pos`, `/api/auth`, `/api/health` or `/api/webhooks` (meta-test) |

## 5. Data model changes
**None.** No migration.
- `audit_logs.source` keeps its values `'admin'` / `'pos'`. They now mean "which area the request came through", which is exactly what they meant in practice. Old rows stay valid.
- `users`, `orders`, `stock_movements` etc. are untouched.

## 6. Backend design

### 6.1 New layout
```
backend/
  shopdesk/                 # NEW — the single Flask app
    __init__.py             # create_app(): builds base app, registers both areas
    areas.py                # Area type, AREA_ROLES, area_blueprint() helper
  admin_area/               # was admin_api/   (routes unchanged except prefixes)
    routes/ users.py products.py pricing.py audit.py orders.py reports.py
    cli.py                  # promote-admin
  pos_area/                 # was pos_api/
    routes/ products.py cart.py orders.py
  core/                     # unchanged business logic; app_factory/security/hardening adjusted
  api/index.py              # Vercel entry: `from shopdesk import create_app; app = create_app()`
  migrations/               # unchanged; now run with `flask --app shopdesk db ...`
```
Folder renames (`admin_api` → `admin_area`, `pos_api` → `pos_area`) make the new meaning obvious. They are done with `git mv` so history is kept.

### 6.2 URL map
Every route keeps its handler, role list and behaviour; only the prefix changes.

| Before (server) | After |
|---|---|
| `GET /api/health` (both) | `GET /api/health` (public) |
| `GET /api/auth/me` (both, role ceiling per server) | `GET /api/auth/me`, any staff role. Response gains `"areas": ["admin","pos"]` or `["pos"]` |
| `POST /api/webhooks/clerk` (admin) | `POST /api/webhooks/clerk` (public, svix-signed) |
| admin `/api/users…` | `/api/admin/users…` |
| admin `/api/categories`, `/api/products…` | `/api/admin/categories`, `/api/admin/products…` |
| admin `/api/pricing/…` | `/api/admin/pricing/…` |
| admin `/api/audit-logs…`, `/api/products/<id>/audit` | `/api/admin/audit-logs…`, `/api/admin/products/<id>/audit` |
| admin `/api/orders…`, `/api/stock/…` | `/api/admin/orders…`, `/api/admin/stock/…` |
| admin `/api/reports/…` | `/api/admin/reports/…` |
| pos `/api/products`, `/api/products/lookup` | `/api/pos/products`, `/api/pos/products/lookup` |
| pos `/api/cart/quote` | `/api/pos/cart/quote` |
| pos `/api/orders/confirm`, `/reject`, `/<no>/receipt`, `/mine` | `/api/pos/orders/confirm`, `/reject`, `/<no>/receipt`, `/mine` |

Why prefixes are required, not just nice: both servers today have `/api/products` and `/api/orders` with **different** responses (admin includes cost; POS must never). The prefix keeps them apart and makes "is this a cashier-reachable URL?" visible in the path.

### 6.3 Areas and role checks (`shopdesk/areas.py`, `core/security.py`)
```python
Area = Literal["admin", "pos"]
AREA_ROLES: dict[Area, frozenset[str]] = {
    "admin": frozenset({"admin", "manager"}),
    "pos":   frozenset({"admin", "manager", "cashier"}),
}

def area_blueprint(area: Area, name: str, prefix: str) -> Blueprint:
    bp = Blueprint(name, import_name, url_prefix=f"/api/{area}{prefix}")
    bp.shopdesk_area = area      # read by require_role / limits / audit
    return bp
```
- `require_role(*roles)` reads the area from the matched blueprint (`request.blueprint` → registered blueprint → `shopdesk_area`) instead of `current_app.config["SHOPDESK_SERVER"]`. Allowed = `roles ∩ AREA_ROLES[area]`, exactly as today.
- **Fail closed:** if a guarded route has no area (programming mistake), `require_role` raises 500 in tests and refuses the request. A meta-test makes this impossible to ship.
- `/api/auth/me` has no area; it allows all three roles and returns the areas the user may open.
- The 403 messages stay the same ("Your account can't use the Admin Console" / "…Billing Counter"), and `auth.role_denied` audit rows keep being written with `source = area`.
- `ActorContext.source` = the area. Audit rows therefore still say `admin` or `pos`.

### 6.4 Token checks (`azp`)
- One setting `AUTHORIZED_PARTIES` (exact origins, comma-separated). Production: just `https://shop.<domain>`. Dev: `http://localhost:5173`.
- Signature, expiry, `nbf`, issuer and `azp` checks in `clerk_auth.verify_session_token` are unchanged.
- Replaces `ADMIN_AUTHORIZED_PARTIES` / `POS_AUTHORIZED_PARTIES`.

### 6.5 Request-size limits (per area)
Flask has one global `MAX_CONTENT_LENGTH`, so:
- Global `MAX_CONTENT_LENGTH` = `MAX_UPLOAD_MB` (4 MB, under Vercel's ~4.5 MB function body cap).
- A `before_request` hook rejects with **413** any request whose `Content-Length` (or streamed body) is over **256 KB**, unless the endpoint is on a tiny allow-list of upload routes (`POST /api/admin/products/<id>/image`, `POST /api/admin/products` when it carries an image).
- Result: POS keeps its 256 KB limit, admin JSON gets the same 256 KB, and only the image routes accept up to 4 MB. This is **stricter** than today.

### 6.6 Rate limits (`core/hardening.py`)
- One limiter, Redis in production (`rediss://`, unchanged), key prefix `shopdesk`.
- Identity: verified Clerk `sub` (with the one `AUTHORIZED_PARTIES`), else client IP. Unchanged logic.
- Buckets keep the same quotas but are **per area**, so heavy admin exports can't eat the counter's quota:

| Bucket | Path rule | Limit |
|---|---|---|
| `pos:quote` | `/api/pos/cart/quote` | 300/min |
| `pos:writes` | other `/api/pos/*` writes | 120/min |
| `admin:writes` | `/api/admin/*` writes | 120/min |
| `admin:export` | `/api/admin/**.csv` | 5/min |
| `webhook` | `/api/webhooks/*` | 60/min |
| `auth` (new) | `/api/auth/me` | 60/min per IP when no valid token (slows token-guessing noise) |

- Unchanged: 429 + `Retry-After`, GET/HEAD/OPTIONS exempt except CSV, Redis errors fail closed.

### 6.7 CORS and headers
- Web and API are on the **same origin**, in production (one Vercel domain) and in dev (Vite proxies `/api` to Flask). So **CORS is switched off**: no `Access-Control-Allow-Origin` header is sent at all. A page on any other origin can't read API responses. This is stricter than an allow-list. `flask-cors` is removed from requirements.
- API response headers from `install_headers` (nosniff, DENY framing, `default-src 'none'` CSP, `no-store`, HSTS in prod) stay unchanged.
- Settings `ADMIN_CORS_ORIGINS` / `POS_CORS_ORIGINS` are removed.

### 6.8 App factory
`core/app_factory.build_base_app()` loses the `server` parameter:
- app name `shopdesk`, `SHOPDESK_SERVER` config removed;
- logging tag `shopdesk` (the area is added per request to the log record);
- health blueprint reports `{"status":"ok","app":"shopdesk"}`;
- production `DEBUG=False` / `PROPAGATE_EXCEPTIONS=False` unchanged.

`shopdesk.create_app()`:
```python
def create_app(settings=None):
    app = build_base_app(settings)
    migrate.init_app(app, db, directory="migrations")
    app.register_blueprint(make_auth_blueprint())      # /api/auth
    app.register_blueprint(webhooks.bp)                # /api/webhooks
    for bp in ADMIN_BLUEPRINTS: app.register_blueprint(bp)   # /api/admin/*
    for bp in POS_BLUEPRINTS:   app.register_blueprint(bp)   # /api/pos/*
    register_cli(app)                                  # promote-admin
    install_body_limits(app); install_rate_limits(app)
    return app
```
Imports stay lazy-friendly (no network or DB work at import time) for cold starts.

### 6.9 Vercel entry
`backend/api/index.py` becomes three lines: add `backend/` to `sys.path`, `from shopdesk import create_app`, `app = create_app()`. `SHOPDESK_SERVER` is removed. Where this file lives depends on §8.2.

## 7. Frontend design

### 7.1 One app: `frontend/web`
```
frontend/
  packages/shared/          # unchanged: api client, auth, money, ui, theme
  web/                      # NEW (replaces admin-web + pos-web)
    src/
      main.tsx  App.tsx  router.tsx
      areas/
        admin/              # everything from admin-web/src (pages, features, Layout)
        pos/                # everything from pos-web/src (BillingPage, cart, orders, print CSS)
      landing/              # role-based redirect + "choose area" screen
    vite.config.ts  vercel.json? (see §8)  index.html
```
Files are moved with `git mv`; component code stays the same except imports and API paths.

### 7.2 Routes and flow
| URL | Who | What |
|---|---|---|
| `/` | signed out | Clerk sign-in (same `SignInPage`) |
| `/` | signed in | **Cashier → `/pos`**. Admin/manager → `/admin` (last used area is remembered in `localStorage`) |
| `/pos/*` | admin, manager, cashier | Billing Counter (today's pos-web, unchanged hotkeys F2/F3/F4/F8/F9/Esc/N) |
| `/admin/*` | admin, manager | Admin Console (today's admin-web; `/admin/products`, `/admin/orders/:id`, …) |
| `/admin/*` | cashier | "No access to the Admin Console" screen (today's `WrongAppScreen`) + "Go to Billing Counter" button. The API would refuse anyway |
| anything else | — | Not-found page with a link home |

- **Area switcher:** admins/managers see "Billing Counter ↔ Admin Console" in the header, so a manager can bill without opening another site.
- **Lazy areas:** `router.tsx` loads `areas/admin` and `areas/pos` with `React.lazy`. A cashier's browser only downloads the shell + POS chunk; the admin JavaScript is never fetched because the area guard redirects before the lazy import runs. Build check: the POS chunk must not import anything from `areas/admin` (ESLint `no-restricted-imports` rule between areas).
- **Guards:** `AuthGate` → `useMe()` → `AreaGuard area="admin" | "pos"` using `me.areas` from `/api/auth/me`. UI guards are for convenience only; the API is the real check.
- **API client:** `createApiClient` gets a base path instead of a base URL: `/api/admin` or `/api/pos` (plus `/api/auth` for `me`). `VITE_API_BASE_URL` is no longer needed (same origin).
- **Printing:** receipt print CSS stays scoped to the POS area.
- **Hotkeys:** registered only while the POS area is mounted, so they never fire on admin pages.

### 7.3 Dev server
- One Vite server on **5173**, `server.proxy = { '/api': 'http://localhost:5001' }`.
- `.claude/launch.json`: 2 configs (`api` 5001, `web` 5173), `autoPort: false`.

## 8. Deployment design (replaces spec 10 §1 and §3.4)

### 8.1 Shape
```
https://shop.<domain>
  ├─ /assets/*, /index.html     → static files from the Vite build (CDN)
  ├─ /api/*                     → one Python function (Flask app `shopdesk`), region sin1
  └─ /admin/*, /pos/*, /        → SPA fallback → /index.html
```
| Piece | Where |
|---|---|
| Vercel project | `shopdesk`, Root Directory = **repo root** |
| Database | Neon `main`, pooled URL with `shopdesk_app` (unchanged) |
| Auth | Clerk production instance, allowed origin = `https://shop.<domain>` only |
| Images | Cloudinary (unchanged) |
| Rate limits | Upstash Redis (unchanged), connected to the one project |
| CI / migrations / backups | GitHub Actions (unchanged, command renamed) |

### 8.2 Root `vercel.json` (draft; verify against current Vercel docs before use)
```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "installCommand": "npm ci --prefix frontend",
  "buildCommand": "npm run build --prefix frontend -w web",
  "outputDirectory": "frontend/web/dist",
  "functions": { "api/index.py": { "maxDuration": 10 } },
  "regions": ["sin1"],
  "rewrites": [
    { "source": "/api/(.*)", "destination": "/api/index" },
    { "source": "/(.*)", "destination": "/index.html" }
  ],
  "headers": [ { "source": "/(.*)", "headers": [ "…same security headers as today, CSP generated per domain…" ] } ]
}
```
- Vercel looks for Python functions in the project's `api/` folder, so a **root** `api/index.py` imports from `backend/`, and a root `requirements.txt` contains `-r backend/requirements.txt`. (Exact handling of Python deps in a mixed Node + Python project must be checked against Vercel's current docs during implementation; a test deploy to a Preview is part of the tasks.)
- Static files are served before rewrites, so `/assets/*.js` is never sent to Flask or to `index.html`.
- `/api/*` responses keep the strict API headers from Flask; HTML gets the web CSP.

### 8.3 Web CSP (one policy)
```
default-src 'self'; script-src 'self' https://clerk.<domain> https://challenges.cloudflare.com;
connect-src 'self' https://clerk.<domain>; img-src 'self' data: blob: https://img.clerk.com https://res.cloudinary.com;
style-src 'self' 'unsafe-inline'; frame-src https://challenges.cloudflare.com; worker-src 'self' blob:;
frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'
```
Simpler than today: `connect-src` no longer lists two API hosts because the API is `'self'`. `scripts/security/configure-web-headers.mjs` writes this into the one root `vercel.json`; `frontend/scripts/check-production-env.mjs` checks it (and no longer requires `VITE_API_BASE_URL`).

### 8.4 Environment variables (one project)
| Variable | Change |
|---|---|
| `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `CLERK_SECRET_KEY`, `CLERK_JWT_KEY`, `CLERK_WEBHOOK_SIGNING_SECRET`, `CLOUDINARY_URL`, `RATELIMIT_STORAGE_URI`, `MAX_UPLOAD_MB`, `LOG_LEVEL`, `APP_ENV` | Unchanged, set **once** |
| `AUTHORIZED_PARTIES` | **New**, replaces `ADMIN_/POS_AUTHORIZED_PARTIES` |
| `ADMIN_CORS_ORIGINS`, `POS_CORS_ORIGINS`, `SHOPDESK_SERVER`, `VITE_API_BASE_URL` | **Removed** |
| `VITE_CLERK_PUBLISHABLE_KEY` | Unchanged (one value) |

Production guards in `core/config.py` keep all checks (live keys, `rediss://`, `shopdesk_app`, TLS, no placeholders) and apply the exact-HTTPS-origin check to `AUTHORIZED_PARTIES`. An old variable name present in the environment raises a clear startup error ("ADMIN_AUTHORIZED_PARTIES was replaced by AUTHORIZED_PARTIES"), so a half-updated `.env` can't silently weaken anything.

### 8.5 Clerk changes
- Allowed origins: only `https://shop.<domain>` (dev: `http://localhost:5173`).
- Webhook URL: `https://shop.<domain>/api/webhooks/clerk`.
- Invite-only, `metadata` session claim, session lifetime ≈ one shift: unchanged.

### 8.6 Optional extra wall: Vercel Firewall
Because admin and POS now share a domain, the owner can (plan permitting) add a Firewall custom rule: *deny `/admin*` and `/api/admin*` unless the client IP is the shop's IP / owner's home IP*. Paths make this easy. Not required; the role checks are the main control.

## 9. Security after the change

| Threat | Before | After |
|---|---|---|
| Cashier calls an admin URL with their token | Route absent on POS server; `azp` wrong on admin server; role check | **Role ceiling per area** (`AREA_ROLES["admin"]` excludes cashier) → 403 + `auth.role_denied` audit row. Proven by a test that calls **every** `/api/admin/*` route as a cashier |
| Cashier opens `/admin` in the browser | Different site; would get "wrong app" screen | Area guard shows "No access"; admin JS chunk never downloaded |
| Cost price leaks to the counter | POS serializers + test | Same serializers; test runs over every `/api/pos/*` route and fails on any `cost`, `profit`, `margin` key |
| A new route forgets its guard | Meta-test (default deny) | Same meta-test **plus**: every route must sit under an allowed prefix, and every `/api/admin` or `/api/pos` route must have an area |
| Other website reads the API (CORS) | Allow-list of 2 origins | No CORS headers at all → no other origin can read responses |
| CSRF | Bearer tokens, no cookies | Unchanged |
| Token from another app (`azp`) | Each API trusts only its own frontend | Only one frontend exists; `azp` must equal it |
| Big request to POS | 256 KB server cap | 256 KB for everything except the image routes (4 MB) |
| Counter traffic starved by admin exports | Separate servers | Separate rate-limit buckets per area |
| Bad deploy | Could break one server only | Breaks both; CI gate + Instant Rollback |
| Price tampering, overselling, audit tampering, uploads, SQLi, CSV injection, XSS | spec 06/07/05/03/09 | **Unchanged** (business code untouched) |

## 10. Tasks
Each step keeps all tests green before moving on. Commit after each group.

**A. Backend (no behaviour change for business logic)**
- [x] 1. `git mv backend/admin_api backend/admin_area`, `git mv backend/pos_api backend/pos_area`; add `backend/shopdesk/` with `create_app()` and `areas.py`.
- [x] 2. Switch every admin/pos blueprint to `area_blueprint(...)` with the new prefixes (§6.2). Move the webhook blueprint to `/api/webhooks` (no area, `@public`).
- [x] 3. `core/security.py`: `SERVER_ROLES` → `AREA_ROLES`, area read from the blueprint, fail closed when missing. `/api/auth/me` returns `areas`.
- [x] 4. `core/config.py`: `AUTHORIZED_PARTIES`, remove CORS/`SHOPDESK_SERVER` settings, renamed-variable error, production guards updated.
- [x] 5. `core/app_factory.py`: remove `server` param and CORS; `core/hardening.py`: per-area buckets, body-size hook (§6.5); remove `flask-cors` from requirements.
- [x] 6. `api/index.py` + root `api/index.py` / `requirements.txt` / `vercel.json` per §8.2.
- [x] 7. Tests: one `app` fixture; update URLs; rewrite `test_route_security` for areas (§11); delete the "two apps" fixtures.

**B. Frontend**
- [ ] 8. Create `frontend/web` (Vite, TS, Tailwind, Vitest config copied from admin-web); `git mv` admin-web/src → `web/src/areas/admin`, pos-web/src → `web/src/areas/pos`.
- [ ] 9. New `router.tsx` with lazy areas, `AreaGuard`, landing redirect, area switcher, not-found page.
- [ ] 10. API client: base paths `/api/admin`, `/api/pos`, `/api/auth`; drop `VITE_API_BASE_URL`; Vite dev proxy.
- [ ] 11. ESLint `no-restricted-imports` between `areas/admin` and `areas/pos`; remove `admin-web`/`pos-web` workspaces; update `package.json` scripts.
- [ ] 12. Move/adjust the 66 frontend tests; add guard/redirect tests (§11).

**C. Tooling, CI and docs**
- [ ] 13. `.claude/launch.json` (2 configs), `scripts/dev.ps1`, `scripts/smoke.ps1` (one base URL), `configure-web-headers.mjs`, `check-production-env.mjs`.
- [ ] 14. `.github/workflows/ci.yml` (one web build), `migrate.yml` (`flask --app shopdesk db upgrade`), `backup.yml` unchanged.
- [ ] 15. Docs: `CLAUDE.md`, `README.md`, `SETUP_GUIDE.md` (env table, ports, commands, troubleshooting), `MANUAL_DEPLOYMENT.md` (one project), `.env.example`, `context/architecture.md` (§1, §3, §7, §10, §11, new ADR A14 superseding A1/A11/A12, A9 reworded to "1 Vercel project"), `ai-workflow-rules.md` (rules mentioning "each API"), spec 10 rewritten for one project, spec 09 checklist wording ("each API rejects the other app's tokens" → "every admin route refuses a cashier"), `progress-tracker.md`.
- [ ] 16. Preview deploy on Vercel (Hobby is fine for this) with the Neon `dev` branch and Clerk dev keys to confirm the mixed static + Python build works. Owner does this step or approves it.

## 11. Acceptance criteria
- [ ] `flask --app shopdesk run -p 5001` + `npm run dev -w web` is the whole local stack; the owner signs in at `http://localhost:5173` and lands on `/admin`; a cashier signs in and lands on `/pos`.
- [ ] A full sale (quote → discount → confirm) works, stock drops, and `/admin/orders` shows it with an `order.confirm` audit row whose `source` is `pos`.
- [ ] Cashier: opening `/admin` shows "No access", the network tab shows **no** admin chunk downloaded, and calling any `/api/admin/*` URL with their token returns 403 `ROLE_NOT_ALLOWED` plus an `auth.role_denied` audit row.
- [ ] No `/api/pos/*` response contains cost/profit fields.
- [ ] API responses have no `Access-Control-Allow-Origin` header.
- [ ] A 300 KB JSON body to `/api/pos/cart/quote` → 413; a 3 MB image to the image route → accepted.
- [ ] All backend tests (≈240 + new) and frontend tests pass; lint, typecheck, build, `pip-audit`, `npm audit`, gitleaks clean.
- [ ] A Vercel Preview of the single project serves `/`, `/admin/products` (deep link), `/pos`, `/api/health`, and `/api/auth/me` without a token → 401.
- [ ] No business-logic file in `core/services`, `core/pricing.py`, `core/models` or `migrations/` changed (diff check).

## 12. Tests
- **Route meta-tests (rewritten):**
  - every route has `@require_role` or `@public`;
  - every path starts with one of `/api/admin/`, `/api/pos/`, `/api/auth/`, `/api/health`, `/api/webhooks/`;
  - every `/api/admin/*` and `/api/pos/*` view belongs to a blueprint with a matching area;
  - no `/api/admin/*` route allows `cashier` (static check on the role lists).
- **Live role sweep:** for every `/api/admin/*` route, request as a cashier (valid token) → 403, never 200/400/404. For every `/api/pos/*` route as cashier → not 403.
- **No-cost sweep:** call each `/api/pos/*` GET/POST with valid data and scan the JSON recursively for `cost`, `cost_price`, `profit`, `margin`.
- **azp:** a token whose `azp` isn't in `AUTHORIZED_PARTIES` → 401 on both areas.
- **Body limits, rate-limit buckets per area, CORS absent:** new hardening tests.
- **Config:** old variable names raise; production requires exact HTTPS `AUTHORIZED_PARTIES`.
- **Frontend:** cashier redirected from `/admin` (and admin chunk import not called); admin lands on last area; area switcher hidden for cashiers; POS hotkeys inactive on admin pages; existing page tests moved and green.

## 13. Rollback plan
- The work happens on a branch `feat/single-server`; `main` keeps the 4-project layout until the owner approves the merge.
- No database changes, so going back is a plain `git revert` of the merge.
- Nothing is deployed to production by this spec.

## 14. Open questions (for the owner)
1. **Domain shape:** one app at `shop.<domain>`, or at the apex `<domain>`? (Recommendation: `shop.<domain>`, leaving the apex free for a public shop page later.)
2. **Folder names:** OK to rename `admin_api`/`pos_api` → `admin_area`/`pos_area` and `admin-web`/`pos-web` → `web`? (Recommendation: yes, the old names would be misleading.)
3. **Landing for admin/manager:** always `/admin`, or remember the last area used? (Recommendation: remember last area.)
4. **Firewall IP rule for `/admin`** (§8.6): want it at go-live, or later?
5. Branch-based work (`feat/single-server`, merged when green) OK, or straight on `main` like specs 01–08?

## 15. Possible follow-ups (not in this spec)
- Counter "kiosk mode": a cashier device that only ever opens `/pos`, with an idle lock after N minutes.
- Per-area Sentry/log tagging if logs get busy.

Owner approved preserving existing env names and all required Clerk fraud-protection/Google Fonts CSP hosts. Spec 09 baseline: e7137ae.
