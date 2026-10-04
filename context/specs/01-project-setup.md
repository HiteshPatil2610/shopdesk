# Spec 01 — Project Setup

**Status:** ✅ Done (2026-10-04) · **Depends on:** — (needs the accounts from SETUP_GUIDE §3) · **Server(s):** both

## 1. Goal
A runnable skeleton: the shared `core` package connected to **Neon** (`dev` branch), two Flask APIs (admin :5001, pos :5002) with health checks, two React apps (admin :5173, pos :5174) that call them, and tooling (lint, format, tests, CI) for both sides. Nothing business-related yet.

## 2. User stories
- As a **developer**, I can run one command and get both APIs and both web apps running locally against Neon.
- As a **developer**, I can run lint and tests for the backend and frontend with one command each, locally and in GitHub Actions.

## 3. Scope
**In:** repo layout (architecture §3), git init + `.gitignore`, config loading, Neon-aware DB engine, Alembic, app factories, health endpoints, error handler skeleton, request-ID middleware, logging, Vite apps with Tailwind + shared preset + proxy, npm workspaces, pre-commit, `ci.yml`, root README.
**Out:** Clerk auth (spec 02), Cloudinary (spec 03), real models (except an empty baseline), deployment (spec 10).

## 4. Business rules touched
None directly. Sets up `core/money.py` (BR-1) with `q2()` and its tests, so float can never sneak in.

## 5. Data model changes
- Alembic initialised under `backend/migrations`, baseline revision `0001_baseline` (empty).
- Applied to the Neon **`dev`** branch via `DATABASE_URL_UNPOOLED`.
- Tests use the local Postgres 18 database `shopdesk_test` (or a Neon `test` branch).

## 6. API
| Method | Path | Server | Role | Response |
|---|---|---|---|---|
| GET | /api/health | admin, pos | public | `{"status":"ok","server":"admin","db":"ok","version":"0.1.0"}` |

`db` is `"error"` (HTTP 503) if `SELECT 1` fails. The health check must stay cheap: the POS also calls it once on load to pre-warm the serverless function.

## 7. UI
- admin-web: placeholder page "ShopDesk Admin" showing the health result as a badge.
- pos-web: placeholder page "ShopDesk Billing" showing the health result.
- Both use the shared Tailwind v4 theme (`@shopdesk/shared/theme.css`, ui-context §1).

## 8. Tasks
- [x] 1. **Repo skeleton.** Folders per architecture §3, `git init`, `.gitignore` (Python, Node, `.env`, `.env.*.local`, `*.db`, `*.dump`, coverage), `.editorconfig`, root `README.md` with quick start. Push to a **private** GitHub repo.
- [x] 2. **Config.** `core/config.py` with pydantic-settings reading the root `.env` locally, or real env vars on Vercel (all vars in SETUP_GUIDE §7). Fail fast with a clear message if a required var is missing. In `production`, also refuse placeholder values. Normalise DB URLs: `postgres://` / `postgresql://` → `postgresql+psycopg://`. Turn `\n` in `CLERK_JWT_KEY` into real newlines. `.env.example` already exists. Keep the two in sync.
- [x] 3. **Backend dependencies.** `backend/pyproject.toml` (black, ruff, mypy, pytest). `requirements.txt`: Flask, SQLAlchemy, psycopg[binary], Flask-Migrate, pydantic, pydantic-settings, PyJWT[crypto], clerk-backend-api, svix, cloudinary, Flask-Limiter, Flask-CORS, Pillow, python-dotenv, gunicorn. `requirements-dev.txt`: pytest, pytest-cov, black, ruff, mypy, pip-audit, factory-boy, freezegun, responses. Pin versions.
- [x] 4. **`core` package.** `db.py`: engine created **lazily** (on first use, not at import, to keep Vercel cold starts fast) from `DATABASE_URL` with the Neon settings from architecture §9 (`pool_pre_ping=True`, `pool_recycle=300`, `pool_size=2`, `max_overflow=3`, `connect_args={"prepare_threshold": None}`). Alembic's `env.py` uses `DATABASE_URL_UNPOOLED`. `errors.py` (AppError + handlers), `money.py` (`q2`, `to_decimal` rejecting float) with tests, logging with request ID.
- [x] 5. **Two Flask apps.** `admin_api.create_app()` / `pos_api.create_app()`: config, error handlers, CORS (own origin list), request ID, `health` blueprint. `wsgi.py` for each. Add `backend/api/index.py` (picks the app with `SHOPDESK_SERVER`) and `backend/vercel.json` per architecture §3, so the same code deploys to Vercel in spec 10. Alembic is wired to admin_api only. Run with `flask --app admin_api run -p 5001` / `flask --app pos_api run -p 5002`.
- [x] 6. **Frontend workspaces.** `frontend/package.json` workspaces. `packages/shared` (Tailwind v4 theme.css, `formatINR`, axios factory that takes a `getToken` function and a base URL, `Button`/`Spinner`). `admin-web` and `pos-web` from the Vite React-TS template + Tailwind + ESLint + Prettier + Vitest. Vite dev proxy per architecture §11. Production uses `VITE_API_BASE_URL`. Add a `vercel.json` to each app with the SPA rewrite (`/(.*)` → `/index.html`). Headers come in spec 09.
- [x] 7. **Dev scripts + CI.** `scripts/dev.ps1` starts both APIs and both Vite servers in separate windows. Pre-commit (black, ruff, prettier, eslint, gitleaks). npm scripts: `lint`, `typecheck`, `test`, `build`. `.github/workflows/ci.yml` (Python 3.12 + `postgres:16` service, Node 22).
- [x] 8. **Smoke tests.** pytest: both `/api/health` return 200 with `db: ok`. Vitest: `formatINR`. Update progress-tracker.

## 9. Acceptance criteria
- [x] With `.env` filled in (Neon `dev` URLs), `flask --app admin_api db upgrade` runs without error and creates `alembic_version` on the Neon `dev` branch.
- [x] `GET http://localhost:5001/api/health` → `server: "admin", db: "ok"`. Same for `:5002` with `server: "pos"`.
- [ ] After 10+ minutes idle (Neon suspended), the next health call still succeeds (pre-ping reconnects).
- [x] `http://localhost:5173` and `:5174` show the placeholders with a green "API OK" badge via the Vite proxy, with no CORS errors.
- [x] The backend venv uses Python 3.12. `pytest`, `ruff`, `black --check`, `npm run lint`, `npm run typecheck` and `npm test` pass locally. *(GitHub Actions run: check after the push.)*
- [x] pytest refuses to run unless `TEST_DATABASE_URL`'s database name ends in `_test` (or the Neon branch is named `test`).
- [x] `core.money.to_decimal(0.1)` raises `TypeError`.
- [x] Missing `DATABASE_URL` → the app refuses to start with a clear message.

## 10. Tests
- Unit: `money.q2` rounding, float rejection, config validation.
- API: health endpoints on both apps, including DB-down → 503.
- Frontend: `formatINR("1234.5") === "₹1,234.50"`.

## 11. Open questions
- ~~Docker or native Postgres?~~ Resolved: Neon for app data (dev + prod branches). Local Postgres 18 is only for fast tests.
