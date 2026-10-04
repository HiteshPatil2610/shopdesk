# ShopDesk — Setup Guide Book

Everything you need to set up ShopDesk on **Vercel + Neon + Clerk + Cloudinary**: which accounts to create, which keys to copy where, every `.env` variable, first run, deployment mapping and troubleshooting.

> Work through the parts in order. Each step ends with a **✅ Check**.
> Commands are for **PowerShell** on Windows.

---

## Contents

1. [The big picture](#1-the-big-picture)
2. [Free tiers and their limits](#2-free-tiers-and-their-limits)
3. [Create the accounts](#3-create-the-accounts)
4. [Install local software](#4-install-local-software)
5. [Local test database](#5-local-test-database)
6. [Where every key comes from](#6-where-every-key-comes-from)
7. [Backend `.env`: every variable explained](#7-backend-env--every-variable-explained)
8. [Frontend env files](#8-frontend-env-files)
9. [First run (after spec 01 is built)](#9-first-run-after-spec-01-is-built)
10. [Daily development workflow](#10-daily-development-workflow)
11. [Production: which variable goes where](#11-production-which-variable-goes-where)
12. [Optional hardware](#12-optional-hardware)
13. [Troubleshooting](#13-troubleshooting)
14. [Readiness checklist](#14-readiness-checklist)

---

## 1. The big picture

```
                  YOUR LAPTOP (development)                     THE INTERNET (production, spec 10)
  admin-web  http://localhost:5173 ─┐                    admin.<domain>      Vercel (static site)
  pos-web    http://localhost:5174 ─┤                    pos.<domain>        Vercel (static site)
  admin_api  http://localhost:5001 ─┤                    admin-api.<domain>  Vercel (Python functions)
  pos_api    http://localhost:5002 ─┘                    pos-api.<domain>    Vercel (Python functions)
          │            │           │                           │        │         │
          ▼            ▼           ▼                           ▼        ▼         ▼
     Neon branch    Clerk dev   Cloudinary               Neon branch  Clerk     Cloudinary
       "dev"        instance    shopdesk-dev/              "main"     production shopdesk/
```

| Service | Job | Cost |
|---|---|---|
| **Neon** | PostgreSQL database (shared by both servers) | Free |
| **Clerk** | Sign-in, passwords, sessions, user accounts | Free |
| **Cloudinary** | Product image storage + thumbnails + CDN | Free |
| **Vercel** | Hosts all 4 pieces: both React websites + both Flask APIs | Hobby free for building and testing. **Pro (~$20/month) for the live shop**, because Hobby is non-commercial |
| **Upstash Redis** | Shared store for API rate limits (production) | Free, via the Vercel Marketplace |
| **GitHub** | Code, CI tests, migrations, nightly backups | Free (private repo) |
| **Domain name** | Required by Clerk's production mode | **~₹100–900/year** |

You only need **GitHub, Neon, Clerk and Cloudinary** to start building. Vercel, Upstash and the domain come later, in spec 10.

---

## 2. Free tiers and their limits

> These limits change. **Check each pricing page before going live.** The figures below are approximate, at the time of writing.

| Service | What's free (approx.) | What it means for ShopDesk |
|---|---|---|
| Neon | 1 project, ~0.5 GB storage, limited compute hours, scales to zero after ~5 min idle, short point-in-time-restore window | Text data for years of a small shop fits easily. First query after idle wakes in under a second |
| Clerk | Tens of thousands of monthly users. Production instance needs **your own domain** | A shop has a handful of staff, so it's effectively unlimited |
| Cloudinary | ~25 monthly "credits" (storage + bandwidth + transformations) | Thousands of product photos are fine |
| Vercel Hobby | Generous function invocations and bandwidth for a small app. Python cold start **~1–3 s** after idle. **~4.5 MB request body limit**. Short log retention. **Personal / non-commercial use only** | Fine for building and testing. Images are resized in the browser to fit the body limit. Upgrade to **Pro** before taking real orders |
| Upstash Redis | A free tier with a monthly command allowance | Rate-limit counters use very little |
| GitHub Actions | ~2,000 minutes/month for private repos | CI + migrations + nightly backup use a small fraction |

> ⚖️ **Vercel licence note:** the free Hobby plan is for personal, non-commercial projects. Building and testing ShopDesk on Hobby is fine. When the shop starts using it for real sales, upgrade the Vercel team to **Pro**. Nothing in the code changes.

---

## 3. Create the accounts

Use one email for all of them, and save every password in a password manager (Bitwarden is free).

### 3.1 GitHub
1. Sign up at https://github.com.
2. Create a **private** repository named `shopdesk` (empty, no README). Spec 01 pushes the code there.

### 3.2 Neon (database)
1. Sign up at https://neon.tech (signing in with GitHub is easiest).
2. **Create project**:
   - Name: `shopdesk`
   - Postgres version: the default (17 is fine)
   - Region: **AWS Asia Pacific (Singapore)**, or the region closest to you. Remember it: the Vercel API functions will run in the matching region (`sin1` = Singapore).
3. The project starts with a branch called **`main`**. This will be **production**.
4. **Branches → Create branch** → name **`dev`**, parent `main`. This is what you develop against.
5. Select the **`dev`** branch → **Connect** button → database `neondb`, role `neondb_owner`:
   - With **Connection pooling ON**, copy the string (its host contains `-pooler`). This is your `DATABASE_URL`.
   - With **Connection pooling OFF**, copy the string. This is your `DATABASE_URL_UNPOOLED`.
6. Neon gives `postgresql://…`. **Change the start to `postgresql+psycopg://`** for both (SQLAlchemy needs it). Keep `?sslmode=require…` at the end.

✅ **Check** (uses the psql you already have from PostgreSQL 18):
```powershell
psql "postgresql://neondb_owner:...@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require" -c "select version();"
```
Use the **plain** `postgresql://` form for psql. It should print `PostgreSQL 17.x`.

### 3.3 Clerk (sign-in)
1. Sign up at https://clerk.com → **Create application**:
   - Name: `ShopDesk`
   - Sign-in options: tick **Username** and **Password**. Email is optional (cashiers may not have one).
2. This creates a **Development** instance (keys start with `pk_test_` / `sk_test_`).
3. **Configure → API keys**, copy:
   - **Publishable key** (`pk_test_…`) → `CLERK_PUBLISHABLE_KEY` and `VITE_CLERK_PUBLISHABLE_KEY`
   - **Secret key** (`sk_test_…`) → `CLERK_SECRET_KEY` (**secret!**)
   - **JWT public key** → choose **PEM** → `CLERK_JWT_KEY` (format: see §7.3)
> 🧭 Clerk renames and moves dashboard pages from time to time. If a menu name below doesn't match, use the **search box at the top of the Clerk dashboard**, or open the direct link given for each step. Pick your ShopDesk app first, because the `~` in the links means "the app you have selected".

4. **User & authentication** page (https://dashboard.clerk.com/~/user-authentication/user-and-authentication): make sure **Username** and **Password** are on. If your cashiers have no email, set email to **not required / optional** (if you can't find that switch, giving each cashier an email works too).
5. **Sessions** page (https://dashboard.clerk.com/~/sessions) → **Customize session token** → in the **Claims** editor paste:
   ```json
   {
     "metadata": "{{user.public_metadata}}",
     "username": "{{user.username}}",
     "name": "{{user.full_name}}"
   }
   ```
   → **Save**. This is Clerk's documented pattern for role-based access. ShopDesk reads the role from `metadata.role` in the token.
   *(The older form `{ "role": "{{user.public_metadata.role}}" }` also works. ShopDesk accepts either.)*
   If your plan lets you change the session lifetime on the same page, set it to about 12 hours (one shift).
6. **Create your owner account**: **Users → Create user** → username `owner`, a strong password, your name.
   Open the user → **Metadata → Public** → set:
   ```json
   { "role": "admin" }
   ```
7. **Turn off public sign-up.** Open the **Access mode** page: in the left sidebar it's under **User & authentication → Access mode**, or go straight to https://dashboard.clerk.com/~/user-authentication/access-mode.
   You'll see three options: **Open** (the default; anyone can sign up), **Invite-only** and **Waitlist**. Choose **Invite-only** → **Save**.
   *(Older Clerk docs and screenshots called this "Restrictions → Sign-up mode → Restricted". It's the same setting under a new name.)*
   After this, accounts can only be created by you in **Users → Create user**, by the ShopDesk Users page (through Clerk's Backend API), or through an invitation. Manual creation still works in Invite-only mode.
8. Webhooks: **skip for local development.** Clerk can't reach your laptop, and ShopDesk syncs users "just in time" instead. You'll add the webhook in spec 10.

✅ **Check:**
- Clerk dashboard → Users shows `owner` with public metadata `{"role":"admin"}`.
- Access mode page shows **Invite-only**.
- Sessions page → Customize session token shows the `metadata` claim.

### 3.4 Cloudinary (images)
1. Sign up at https://cloudinary.com (free plan).
2. **Dashboard / Settings → API Keys**: copy the **API environment variable**. It looks like `CLOUDINARY_URL=cloudinary://123456789012345:AbCdEf...@your-cloud-name`
   → paste the part after `=` into `CLOUDINARY_URL` (**secret!**).
   ⚠️ The dashboard shows it as `cloudinary://<your_api_key>:<your_api_secret>@your-cloud`. **Replace the `<…>` parts** with the real **API Key** and **API Secret** listed on the same page (click the eye icon to reveal the secret). The final value has no `<` or `>`.
3. You don't need to create folders. They're created on the first upload (`shopdesk-dev/products` for dev).

✅ **Check:** the dashboard shows your **cloud name**, and it matches the end of `CLOUDINARY_URL`.

### 3.5 Later, for spec 10 (don't do these yet)
| Account | What for |
|---|---|
| **Domain registrar** (any: Namecheap, GoDaddy, Hostinger, BigRock, Cloudflare Registrar) | Buy e.g. `yourshop.in`. Clerk production needs it. DNS can stay at the registrar or move to Vercel DNS |
| **Vercel** (https://vercel.com, sign in with GitHub) | Import the repo **4 times** (admin-web, pos-web, admin-api, pos-api). See spec 10 §3.4 |
| **Upstash Redis** (via Vercel → Storage / Marketplace) | Free Redis for production rate limits, connected to both API projects |
| **Clerk production instance** | Created inside your Clerk app once the domain is ready |

---

## 4. Install local software

| Tool | Needed version | Your machine (checked 2026-10-04) | Action |
|---|---|---|---|
| Python | **3.12** (3.11+) | 3.10.11 ❌ | Install 3.12 (below). 3.10 can stay for other projects |
| Node.js + npm | 20+ | v26.4.0 ✅ | — |
| Git | any | 2.55 ✅ | Set name/email (below) |
| PostgreSQL (local) | 16+ | 18.4, running ✅ | Used **only for automated tests** (§5) |
| VS Code | any | 1.140 ✅ | Extensions (below) |

### 4.1 Python 3.12
```powershell
winget install Python.Python.3.12
```
✅ **Check:** reopen PowerShell, run `py -0p`, and confirm `-3.12` is listed.

### 4.2 Git identity
```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global core.autocrlf true
git config --global init.defaultBranch main
```

### 4.3 VS Code extensions
```powershell
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension charliermarsh.ruff
code --install-extension ms-python.black-formatter
code --install-extension dbaeumer.vscode-eslint
code --install-extension esbenp.prettier-vscode
code --install-extension bradlc.vscode-tailwindcss
code --install-extension mtxr.sqltools
code --install-extension mtxr.sqltools-driver-pg
code --install-extension mikestead.dotenv
code --install-extension eamodio.gitlens
```

### 4.4 Allow venv activation in PowerShell (one time, your user only)
If `.\venv\Scripts\Activate.ps1` says "running scripts is disabled", run this yourself:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 4.5 Not needed any more
Docker, Nginx, Gunicorn config and generating your own JWT secrets: Vercel and Clerk replace them. The Vercel CLI is optional (`npm i -g vercel`). It's handy for `vercel env pull`, but everything can be done in the dashboard.

---

## 5. Test database

**What it is:** the automated tests (`pytest`) **wipe their database and rebuild it on every run**, so they must never touch your real data. They use a separate, throwaway database called **`shopdesk_test`**, and `TEST_DATABASE_URL` points to it. The app refuses to run tests on any database whose name doesn't end in `_test`.

### Option A: on Neon (✅ what this project uses, already done on 2026-10-04)
A database `shopdesk_test` sits in the same Neon project, next to your real `neondb`. It's a completely separate database. `TEST_DATABASE_URL` is your **direct** (non-pooler) Neon URL with the database name changed from `/neondb` to `/shopdesk_test`:
```ini
TEST_DATABASE_URL=postgresql+psycopg://neondb_owner:PASSWORD@ep-xxxx.ap-southeast-1.aws.neon.tech/shopdesk_test?sslmode=require&channel_binding=require
```
To recreate it by hand: Neon console → your project → branch `dev` → **Databases → New database** → name `shopdesk_test`, owner `neondb_owner`.

### Option B: local PostgreSQL (faster tests, optional)
Needs your local `postgres` superuser password (the one you chose when installing PostgreSQL).
```powershell
psql -U postgres -h localhost
```
```sql
CREATE ROLE shopdesk WITH LOGIN PASSWORD 'pick_a_password';
CREATE DATABASE shopdesk_test OWNER shopdesk ENCODING 'UTF8' TEMPLATE template0;
\q
```
Then set `TEST_DATABASE_URL=postgresql+psycopg://shopdesk:pick_a_password@localhost:5432/shopdesk_test`.

✅ **Check (either option):** `cd backend; .\venv\Scripts\pytest -q` shows **0 skipped**.

> GitHub Actions doesn't use either. It starts its own temporary Postgres for every CI run.

---

## 6. Where every key comes from

| Value | Where to find it | Goes into | Secret? |
|---|---|---|---|
| Neon pooled URL (`dev`) | Neon → branch `dev` → Connect → pooling **on** | `DATABASE_URL` | 🔒 yes |
| Neon direct URL (`dev`) | Neon → branch `dev` → Connect → pooling **off** | `DATABASE_URL_UNPOOLED` | 🔒 yes |
| Clerk publishable key | Clerk → Configure → API keys | `CLERK_PUBLISHABLE_KEY`, `VITE_CLERK_PUBLISHABLE_KEY` | no (public by design) |
| Clerk secret key | Clerk → Configure → API keys | `CLERK_SECRET_KEY` | 🔒 **yes, the most sensitive one** |
| Clerk JWT public key (PEM) | Clerk → Configure → API keys → JWT public key | `CLERK_JWT_KEY` | no (public key), but keep it in env |
| Clerk webhook secret | Clerk → Webhooks → endpoint → Signing secret (spec 10) | `CLERK_WEBHOOK_SIGNING_SECRET` | 🔒 yes |
| Cloudinary URL | Cloudinary → Settings → API Keys → API environment variable | `CLOUDINARY_URL` | 🔒 yes |

---

## 7. Backend `.env`: every variable explained

### 7.1 Create it
```powershell
cd E:\Personal-Projects\ShopDesk
Copy-Item .env.example .env
code .env
```
- `.env` holds real secrets and is **never committed**.
- `.env.example` has **placeholders only** and **is committed**. When you add a variable, add it to both, plus `core/config.py` and this guide.
- Both Flask servers read the same root `.env` locally. In production, each Vercel project has its own copy of the variables it needs (§11).

### 7.2 Variable reference

#### General
| Variable | Required | Dev value | What it does |
|---|---|---|---|
| `APP_ENV` | ✅ | `development` | `development` \| `test` \| `production`. Production turns on strict checks (refuses `sk_test_` keys and placeholders) |
| `LOG_LEVEL` | — | `DEBUG` | `INFO` in production |
| `TZ_DISPLAY` | — | `Asia/Kolkata` | Timezone for display, "today" in reports and the daily invoice reset |
| `CURRENCY` | — | `INR` | ₹ formatting |

#### Database (Neon)
| Variable | Required | Dev value | What it does |
|---|---|---|---|
| `DATABASE_URL` | ✅ | Neon `dev` **pooled** URL, starting `postgresql+psycopg://` | Used by both running servers |
| `DATABASE_URL_UNPOOLED` | ✅ (admin) | Neon `dev` **direct** URL, starting `postgresql+psycopg://` | Used by migrations (`flask db upgrade`). Only admin_api needs it |
| `TEST_DATABASE_URL` | ✅ for tests | `postgresql+psycopg://shopdesk:local_test_password@localhost:5432/shopdesk_test` | pytest only. The tests refuse to run unless the DB name ends in `_test` (or the Neon branch is `test`) |
| `DB_POOL_SIZE` | — | `5` | Keep it small (Neon + free tier) |
| `DB_ECHO` | — | `false` | `true` prints every SQL query |

#### Servers
| Variable | Required | Dev value | What it does |
|---|---|---|---|
| `ADMIN_PORT` / `POS_PORT` | — | `5001` / `5002` | Local ports only. Not used on Vercel |
| `SHOPDESK_SERVER` | Vercel only | *(not set locally)* | `admin` or `pos`. Tells `backend/api/index.py` which Flask app to build. Locally, `flask --app admin_api` / `--app pos_api` chooses instead |
| `ADMIN_CORS_ORIGINS` | ✅ | `http://localhost:5173` | Origins allowed to call the Admin API. Comma-separated, never `*` |
| `POS_CORS_ORIGINS` | ✅ | `http://localhost:5174` | Same for the Billing API |

#### Clerk (auth)
| Variable | Required | Dev value | What it does |
|---|---|---|---|
| `CLERK_PUBLISHABLE_KEY` | — | `pk_test_…` | For reference/CLI. The frontends use the `VITE_` copy |
| `CLERK_SECRET_KEY` | ✅ | `sk_test_…` | Backend calls to Clerk (create users, change roles, ban). **Never** put it in frontend code |
| `CLERK_JWT_KEY` | ✅ | PEM public key (§7.3) | Verifies session tokens locally on every request, with no network call |
| `ADMIN_AUTHORIZED_PARTIES` | ✅ | `http://localhost:5173` | admin_api only accepts tokens issued to these frontend origins |
| `POS_AUTHORIZED_PARTIES` | ✅ | `http://localhost:5174` | pos_api only accepts tokens issued to these origins |
| `CLERK_WEBHOOK_SIGNING_SECRET` | prod | *(blank in dev)* | `whsec_…`. Verifies webhook calls from Clerk |

#### Images (Cloudinary)
| Variable | Required | Dev value | What it does |
|---|---|---|---|
| `CLOUDINARY_URL` | ✅ | `cloudinary://KEY:SECRET@CLOUD` | Credentials for uploads/deletes |
| `CLOUDINARY_FOLDER` | ✅ | `shopdesk-dev/products` | Keeps dev and prod images apart (`shopdesk/products` in prod) |
| `MAX_UPLOAD_MB` | — | `4` | Largest image accepted. Must stay under Vercel's ~4.5 MB request limit. The browser shrinks photos before upload anyway |

#### Rate limiting
| Variable | Required | Dev value | What it does |
|---|---|---|---|
| `RATELIMIT_STORAGE_URI` | — | `memory://` | Fine locally. **Production must use Upstash Redis** (`rediss://…`), because Vercel instances don't share memory |

#### Shop details (receipts)
| Variable | Required | Example | What it does |
|---|---|---|---|
| `SHOP_NAME` | ✅ | `Patil General Store` | Receipt header |
| `SHOP_ADDRESS`, `SHOP_PHONE` | — | | Receipt header |
| `SHOP_GSTIN` | — | *(blank)* | For later (GST is post-v1) |
| `RECEIPT_FOOTER` | — | `Thank you! Visit again` | Last line of the receipt |

#### Manual backups from your laptop (optional)
| Variable | Required | Example | What it does |
|---|---|---|---|
| `BACKUP_DIR` | — | `E:/Backups/ShopDesk` | Where `scripts/backup_db.ps1` saves dumps |
| `PG_BIN_DIR` | — | `C:/Program Files/PostgreSQL/18/bin` | Location of `pg_dump.exe` (v18 can dump Neon's v17) |

### 7.3 Formatting gotchas
- **Easiest way to set `CLERK_JWT_KEY`:** let the project fetch it for you. It's Clerk's *public* key, worked out from your publishable key:
  ```powershell
  cd backend
  .\venv\Scripts\python -m core.setup_tools fetch-clerk-key
  ```
  Then restart both API servers. Run it again whenever `CLERK_PUBLISHABLE_KEY` changes (e.g. the production instance). If the key is wrong, the API refuses to start and tells you to run this.
- **`CLERK_JWT_KEY`** is a multi-line PEM. Put it on **one line in double quotes**, with `\n` where the line breaks were:
  ```ini
  CLERK_JWT_KEY="-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqh...\n...IDAQAB\n-----END PUBLIC KEY-----"
  ```
  `core/config.py` turns `\n` back into real newlines. In the Vercel dashboard you can paste the real multi-line PEM.
- **Neon URLs:** change `postgresql://` to `postgresql+psycopg://`, and keep the `?sslmode=require…` part.
- No spaces around `=`. No quotes needed except for the PEM.
- Use forward slashes in Windows paths.
- **Restart both servers** after editing `.env`.
- **Never point your local `.env` at the Neon `main` branch.** That's production data.

---

## 8. Frontend env files

The frontends only hold **public** values. Anything starting with `VITE_` ends up in the browser bundle, so **never put a secret in a `VITE_` variable**.

`frontend/admin-web/.env.development` (committed):
```ini
VITE_APP_TITLE=ShopDesk Admin
VITE_API_PROXY_TARGET=http://localhost:5001
VITE_API_BASE_URL=
```
`frontend/pos-web/.env.development` (committed):
```ini
VITE_APP_TITLE=ShopDesk Billing
VITE_API_PROXY_TARGET=http://localhost:5002
VITE_API_BASE_URL=
```
`frontend/admin-web/.env.development.local` **and** `frontend/pos-web/.env.development.local` (gitignored, one each):
```ini
VITE_CLERK_PUBLISHABLE_KEY=pk_test_xxxxxxxxxxxxxxxx
```
- An empty `VITE_API_BASE_URL` means "same origin", so Vite proxies `/api` to the Flask server in dev.
- In production, each Vercel web project sets `VITE_API_BASE_URL=https://admin-api.<domain>` (or `pos-api`) and the `pk_live_…` key (§11). `VITE_` values are baked in at build time, so **redeploy** after changing them.

---

## 9. First run (after spec 01 is built)

Ask Claude to *"start spec 01"* first. These commands only work once the code exists.

### 9.1 Backend
```powershell
cd E:\Personal-Projects\ShopDesk\backend
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```
✅ `python --version` → 3.12.x

### 9.2 Create the tables on Neon `dev`
```powershell
flask --app admin_api db upgrade
```
✅ Neon console → branch `dev` → Tables shows `alembic_version` (and more tables as the specs progress).

### 9.3 Link your Clerk owner account (after spec 02)
Sign in once at http://localhost:5173. ShopDesk creates your local user record automatically. If you skipped setting the metadata in §3.3 step 6:
```powershell
flask --app admin_api promote-admin --clerk-user-id user_xxxxxxxx
```
(The user ID is shown on the user's page in the Clerk dashboard.)

### 9.4 Frontend
```powershell
cd E:\Personal-Projects\ShopDesk\frontend
npm install
```

### 9.5 Start everything (`scripts\dev.ps1`, or 4 terminals)
| Terminal | Folder | Command | URL |
|---|---|---|---|
| 1 | `backend` (venv on) | `flask --app admin_api run -p 5001 --debug` | http://localhost:5001/api/health |
| 2 | `backend` (venv on) | `flask --app pos_api run -p 5002 --debug` | http://localhost:5002/api/health |
| 3 | `frontend` | `npm run dev -w admin-web` | http://localhost:5173 |
| 4 | `frontend` | `npm run dev -w pos-web` | http://localhost:5174 |

✅ **Check:** both health URLs show `"db": "ok"`. Both sites load, and after spec 02 you can sign in as `owner`.

### 9.6 Run the checks
```powershell
cd E:\Personal-Projects\ShopDesk\backend;  ruff check .; black --check .; pytest -q
cd E:\Personal-Projects\ShopDesk\frontend; npm run lint; npm run typecheck; npm test
```

---

## 10. Daily development workflow

```powershell
cd E:\Personal-Projects\ShopDesk
git pull
cd backend; .\venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt   # if requirements changed
flask --app admin_api db upgrade                          # if migrations changed
cd ..\frontend; npm install                               # if package.json changed
cd ..; .\scripts\dev.ps1
```

**Start a Claude Code session with:**
```
Read context/README.md, context/ai-workflow-rules.md and context/progress-tracker.md.
Tell me where we are, then propose the next task.
```

**Database change:** edit models → `flask --app admin_api db migrate -m "describe change"` → **read the generated file** → `flask --app admin_api db upgrade` (applies to Neon `dev`). Production gets it automatically on the next deploy.

**Fresh dev data:** Neon console → branch `dev` → **Reset from parent** (copies production's current data into dev). Only do this if you're happy for dev to be overwritten.

---

## 11. Production: which variable goes where

Spec 10 does the actual deployment. This table is the map.

There are 4 Vercel projects (spec 10). Add variables in each project → **Settings → Environment Variables**, ticking the **Production** environment only for secrets.

| Variable | Vercel `shopdesk-admin-api` | Vercel `shopdesk-pos-api` | Vercel `shopdesk-admin-web` | Vercel `shopdesk-pos-web` | GitHub secrets |
|---|---|---|---|---|---|
| `SHOPDESK_SERVER` | `admin` | `pos` | | | |
| `APP_ENV=production`, `LOG_LEVEL=INFO`, `TZ_DISPLAY`, `CURRENCY` | ✅ | ✅ | | | |
| `DATABASE_URL` (Neon **main**, **pooled**, `shopdesk_app` role) | ✅ | ✅ | | | |
| `CLERK_SECRET_KEY` (`sk_live_…`), `CLERK_JWT_KEY` (production PEM) | ✅ | ✅ | | | |
| `CLERK_WEBHOOK_SIGNING_SECRET` | ✅ | | | | |
| `ADMIN_AUTHORIZED_PARTIES`, `ADMIN_CORS_ORIGINS` = `https://admin.<domain>` | ✅ | | | | |
| `POS_AUTHORIZED_PARTIES`, `POS_CORS_ORIGINS` = `https://pos.<domain>` | | ✅ | | | |
| `CLOUDINARY_URL`, `CLOUDINARY_FOLDER=shopdesk/products`, `MAX_UPLOAD_MB=4` | ✅ | ✅ | | | |
| `RATELIMIT_STORAGE_URI` (Upstash `rediss://…`) | ✅ | ✅ | | | |
| `SHOP_*`, `RECEIPT_FOOTER` | | ✅ | | | |
| `VITE_CLERK_PUBLISHABLE_KEY` (`pk_live_…`) | | | ✅ | ✅ | |
| `VITE_API_BASE_URL` | | | `https://admin-api.<domain>` | `https://pos-api.<domain>` | |
| `NEON_MIGRATE_URL` (Neon main, **direct**, owner role) | | | | | ✅ |
| `NEON_BACKUP_URL` (Neon main, **direct**, read-only role) | | | | | ✅ |

Notes:
- The running APIs **never** get the direct/owner URL. Only GitHub Actions uses it, to run migrations.
- In Vercel you can paste `CLERK_JWT_KEY` as the real multi-line PEM.
- Production uses **different keys from development**: Clerk `live` keys, the Neon `main` branch and the production Cloudinary folder. Never put production values in the **Preview** or **Development** environments.

---

## 12. Optional hardware

| Item | Notes |
|---|---|
| **USB barcode scanner** | "USB HID / keyboard" mode with an Enter suffix (the default on most). No driver needed. ~₹1,500–3,000 |
| **80mm thermal printer** | Install the driver and make it the default printer on the billing PC. ShopDesk prints via the browser. Chrome's `--kiosk-printing` flag skips the print dialog |
| **Tablet / second PC** | Anything with a modern browser can open `https://pos.<domain>` |
| **Stable internet** | ShopDesk is cloud-based now, so the counter needs internet. Keep a mobile hotspot as backup |

---

## 13. Troubleshooting

| Problem | Fix |
|---|---|
| `py -3.12` → "No suitable Python runtime" | §4.1, then reopen PowerShell |
| `Activate.ps1 cannot be loaded` | §4.4 |
| `psql` not recognised | Add `C:\Program Files\PostgreSQL\18\bin` to PATH |
| `NoSuchModuleError: postgresql.psycopg` or wrong driver | The URL must start with `postgresql+psycopg://` |
| `SSL connection is required` / connection refused to Neon | Keep `?sslmode=require` on the URL. Check you copied the whole string |
| `prepared statement "…" does not exist` | You're on the pooled URL without `prepare_threshold=None`. Check `core/db.py` (spec 01 task 4) |
| Migrations hang or fail on the pooler | Migrations must use `DATABASE_URL_UNPOOLED` (direct) |
| First request after a break is slow (~1 s) | Neon waking from scale-to-zero. That's normal |
| Production API takes 1–3 s on the first call after idle | Vercel serverless cold start. That's normal. If it's much slower, check for heavy imports at module level (spec 10 task 6) |
| Image upload fails with 413 / `FUNCTION_PAYLOAD_TOO_LARGE` | The file is over Vercel's ~4.5 MB limit. Check that the browser-side resize (spec 03) runs before upload |
| Vercel deploy: `SHOPDESK_SERVER must be 'admin' or 'pos'` | Set `SHOPDESK_SERVER` in that API project's environment variables, then redeploy |
| Vercel API returns 404 for `/api/...` | `backend/vercel.json` rewrite is missing, or the project's Root Directory isn't `backend` |
| Deep link like `/products` shows a Vercel 404 | The web app's `vercel.json` SPA rewrite is missing |
| Changed a `VITE_` variable but the site didn't change | `VITE_` values are baked in at build time. Redeploy the web project |
| Rate limits don't seem to apply in production | `RATELIMIT_STORAGE_URI` is still `memory://`. Connect Upstash Redis |
| 401 `TOKEN_WRONG_APP` | `*_AUTHORIZED_PARTIES` doesn't match the exact frontend origin (scheme + host + port, no trailing slash) |
| 401 `TOKEN_INVALID` | `CLERK_JWT_KEY` is wrong, or from the other instance (dev vs prod). Check the `\n` formatting (§7.3) |
| 403 `NO_ROLE_ASSIGNED` / "Your account has no ShopDesk role yet" | Most often the user's **public metadata is empty**: Clerk → Users → the user → Metadata → Public → `{"role":"admin"}` → Save (or run `flask --app admin_api promote-admin --clerk-user-id user_…`). Otherwise the user has no `public_metadata.role`, or the `"metadata": "{{user.public_metadata}}"` session claim (§3.3 step 5) is missing. Sign out and back in after fixing |
| Sign-up form appears, or strangers can create accounts | Clerk Access mode is still **Open**. Set it to **Invite-only** (§3.3 step 7) |
| Can't find a Clerk setting mentioned here | Clerk renames pages. Use the dashboard's search box, or the direct links in §3.3 (select the ShopDesk app first) |
| Clerk sign-in widget is blank in production | CSP blocks Clerk domains. See spec 09 task 1, and check the browser console |
| Image upload: "Image uploads aren't set up… placeholder text" or "Cloudinary rejected the credentials" | `CLOUDINARY_URL` still contains `<your_api_key>`/`<your_api_secret>`, or a wrong key. See §3.4, then restart the API servers |
| Images upload but don't show | Check `thumb_url` in the API response opens in the browser, and that CSP allows `res.cloudinary.com` |
| CORS error in the browser | In dev, use :5173/:5174 (the Vite proxy). In prod, check `*_CORS_ORIGINS` |
| `Address already in use` | `Get-NetTCPConnection -LocalPort 5001 \| Select OwningProcess`, then close that program |
| Tests wiped real data | Impossible if set up right: tests only run on a DB ending in `_test`. Check `TEST_DATABASE_URL` |

---

## 14. Readiness checklist

**Before spec 01**
- [ ] Python 3.12 installed (`py -0p`)
- [ ] Git name/email set. Private GitHub repo `shopdesk` created
- [ ] Neon project `shopdesk` (Singapore) with branches `main` and `dev`
- [ ] `DATABASE_URL` (pooled) + `DATABASE_URL_UNPOOLED` (direct) for **dev** in `.env`, both starting `postgresql+psycopg://`
- [ ] Local `shopdesk_test` DB created. `TEST_DATABASE_URL` set
- [ ] Clerk app created: Username + Password, `metadata` session claim, Access mode **Invite-only**
- [ ] Clerk owner user created with public metadata `{"role":"admin"}`
- [ ] `CLERK_SECRET_KEY`, `CLERK_JWT_KEY`, `*_AUTHORIZED_PARTIES` in `.env`
- [ ] `VITE_CLERK_PUBLISHABLE_KEY` ready for both `.env.development.local` files
- [ ] Cloudinary account created. `CLOUDINARY_URL` + `CLOUDINARY_FOLDER=shopdesk-dev/products` in `.env`
- [ ] `SHOP_NAME` set
- [ ] VS Code extensions installed

**Before spec 10 (deployment)**
- [ ] Domain bought
- [ ] Vercel account (GitHub login). 4 projects imported (spec 10 §3.4)
- [ ] Upstash Redis connected to both API projects
- [ ] GitHub secrets `NEON_MIGRATE_URL` + `NEON_BACKUP_URL` added
- [ ] Vercel team upgraded to **Pro** before real sales
- [ ] Clerk production instance created and DNS verified
- [ ] Production values ready for every row in §11
