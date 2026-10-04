# ShopDesk

Product management and billing for a small shop. There are **two servers sharing one database**:

| App | Who | What |
|---|---|---|
| **Admin Console** (`admin_api` + `admin-web`) | Owner / manager | Products with images, automatic MP/SP pricing, stock, orders, audit log |
| **Billing Counter** (`pos_api` + `pos-web`) | Cashier | Customer name, product code + quantity, discount (MP → SP), confirm or reject |

**Stack:** Flask + SQLAlchemy (Python 3.12) · React 19 + Vite + Tailwind v4 (TypeScript) · Neon Postgres · Clerk · Cloudinary · Vercel.

## Quick start (Windows)

First-time setup (accounts, `.env`, databases) is in **[SETUP_GUIDE.md](SETUP_GUIDE.md)**. After that:

```powershell
# backend
cd backend
py -3.12 -m venv venv
.\venv\Scripts\pip install -r requirements-dev.txt
.\venv\Scripts\flask --app admin_api db upgrade

# frontend
cd ..\frontend
npm install

# run everything (4 windows)
cd ..
.\scripts\dev.ps1
```

| URL | |
|---|---|
| http://localhost:5173 | Admin Console |
| http://localhost:5174 | Billing Counter |
| http://localhost:5001/api/health | Admin API health |
| http://localhost:5002/api/health | POS API health |

## Checks

```powershell
cd backend;  .\venv\Scripts\ruff check .; .\venv\Scripts\black --check .; .\venv\Scripts\mypy; .\venv\Scripts\pytest -q
cd frontend; npm run lint; npm run typecheck; npm test
```

## Project docs

All design docs live in [`context/`](context/README.md): overview, architecture, UI, code standards, AI workflow rules, progress tracker and feature specs.
