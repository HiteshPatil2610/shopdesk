# ShopDesk

Product management and billing for a small shop. There is **one app with two protected areas sharing one database**:

| App | Who | What |
|---|---|---|
| **Admin Console** (`/admin` + `/api/admin`) | Owner / manager | Products with images, automatic MP/SP pricing, stock, orders, audit log |
| **Billing Counter** (`/pos` + `/api/pos`) | Cashier | Customer name, product code + quantity, discount (MP → SP), confirm or reject |

**Stack:** Flask + SQLAlchemy (Python 3.12) · React 19 + Vite + Tailwind v4 (TypeScript) · Neon Postgres · Clerk · Cloudinary · Vercel.

## Quick start (Windows)

First-time setup (accounts, `.env`, databases) is in **[SETUP_GUIDE.md](SETUP_GUIDE.md)**. After that:

```powershell
# backend
cd backend
py -3.12 -m venv venv
.\venv\Scripts\pip install -r requirements-dev.txt
.\venv\Scripts\flask --app shopdesk db upgrade

# frontend
cd ..\frontend
npm ci

# run API and web (background processes; logs in tmp/dev)
cd ..
.\scripts\dev.ps1
```

| URL | Purpose |
|---|---|
| http://localhost:5173 | One sign-in; role-based area landing |
| http://localhost:5173/admin | Admin Console (owner/manager) |
| http://localhost:5173/pos | Billing Counter (all staff) |
| http://localhost:5001/api/health | Single API health |

Vercel deploys two services in one project: `backend` (Flask at `/api/...`) and `frontend` (static Vite app at all other paths). Browser requests stay same-origin; there are no runtime service bindings. For platform routing checks, run `npx vercel@latest dev -L` from the repo root and `scripts/smoke.ps1 -BaseUrl http://localhost:3000`. Add that exact origin to development `AUTHORIZED_PARTIES` and Clerk before testing sign-in; the existing `scripts/dev.ps1` workflow still uses port 5173.

Manual deployment instructions: [MANUAL_DEPLOYMENT.md](MANUAL_DEPLOYMENT.md). Preview and production deployment are owner actions, not yet verified.

## Checks

```powershell
cd backend;  .\venv\Scripts\ruff check .; .\venv\Scripts\black --check .; .\venv\Scripts\mypy; .\venv\Scripts\pytest -q
cd frontend; npm run lint; npm run typecheck; npm test
```

## Project docs

All design docs live in [`context/`](context/README.md): overview, architecture, UI, code standards, AI workflow rules, progress tracker and feature specs.
