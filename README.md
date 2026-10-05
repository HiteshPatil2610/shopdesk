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

Manual deployment instructions: [MANUAL_DEPLOYMENT.md](MANUAL_DEPLOYMENT.md). Preview and production deployment are owner actions, not yet verified.

## Checks

```powershell
cd backend;  .\venv\Scripts\ruff check .; .\venv\Scripts\black --check .; .\venv\Scripts\mypy; .\venv\Scripts\pytest -q
cd frontend; npm run lint; npm run typecheck; npm test
```

## Project docs

All design docs live in [`context/`](context/README.md): overview, architecture, UI, code standards, AI workflow rules, progress tracker and feature specs.
