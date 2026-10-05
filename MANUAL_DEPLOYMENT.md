# Manual deployment — ShopDesk

Prepared 2026-10-05. You carry out the account changes and deployment yourself. This guide matches the repository's single Flask app and single Vite web app, Neon, Clerk, Cloudinary and Upstash. Keep your existing development `.env` on Neon **dev**.

## 1. Decide the production address

Choose one app hostname, for example `shop.example.com` (replace it below with your actual domain).

| Project | Root directory | Address |
|---|---|---|
| shopdesk | repository root (`.`) | https://shop.example.com |

This project serves `/admin`, `/pos` and `/api/*`. Clerk has its own verified Frontend API hostname. Verify current commercial-use terms on [Vercel pricing](https://vercel.com/pricing) before real sales. The supplied backup workflow requires a **private GitHub repository**; artifacts contain customer information. If the code must remain public, move backups into a private repository/storage first.

## 2. Check and push the code

From the project folder, run the checks below. Backend tests wipe ONLY the database named in `TEST_DATABASE_URL`, which must end in `_test`; never substitute the production URL.

```powershell
Set-Location E:\Personal-Projects\ShopDesk\backend
.\venv\Scripts\python.exe -m ruff check .
.\venv\Scripts\python.exe -m black --workers 1 --check .
.\venv\Scripts\python.exe -m mypy
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m pip_audit -r requirements.txt
Set-Location ..\frontend
npm ci
npm run lint
npm run typecheck
npm test
node --test scripts/check-production-env.test.mjs
npm run build -w web
npm audit --omit=dev --audit-level=high
```

Review your diff; commit and push it yourself. Enable branch protection requiring CI. Install the existing pre-commit hooks with `backend\venv\Scripts\pre-commit.exe install` from the repository root. CI scans full Git history with gitleaks and audits dependencies. A failed secret scan requires rotating the exposed credential before addressing the history.

## 3. Create Clerk production authentication

In Clerk, create/select a **production instance**, connect your domain, and add exactly the DNS records Clerk displays. Wait for verification. Configure:

- Access mode **Invite-only**; use username/password as in development.
- Session custom claim: `"metadata": "{{user.public_metadata}}"`.
- Frontend origins: only `https://shop.example.com`.
- Session maximum lifetime: approximately one shift (for example 8 hours). Set inactivity timeout if your plan supports it; confirm the actual dashboard controls available.
- Create a fresh owner account with public metadata `{"role":"admin"}`. Use a strong password and enable MFA where available. Development demo accounts/passwords must not be copied into production.

Save the **live** publishable key (`pk_live_...`), live secret key (`sk_live_...`), PEM JWT verification public key, and Frontend API hostname. Use the public key belonging to this production instance, not the dev key. Create a webhook targeting `https://shop.example.com/api/webhooks/clerk`, subscribing to user.created/user.updated/user.deleted. Save its `whsec_...` signing secret; test delivery after the API is live.

Generate the web CSP for your actual domain and the Clerk Frontend API hostname (hostnames only):

```powershell
Set-Location E:\Personal-Projects\ShopDesk
node scripts/security/configure-web-headers.mjs shop.example.com clerk.example.com
```

This updates **root** `vercel.json` with the exact Clerk host and security headers while preserving the build and routing configuration. API requests stay same-origin (`connect-src self`); the web header rule excludes `/api`, where Flask supplies its stricter CSP. Review and commit the result before deployment. Checked-in development policies are not your production policy. The generator includes Clerk's current fraud protection hosts and Cloudflare challenges; see [Clerk CSP documentation](https://clerk.com/docs/guides/secure/best-practices/csp-headers). Do not add broad `https:` or script `unsafe-inline` to silence errors; identify the blocked host first.

## 4. Prepare Neon production and database roles

Select the production **main** branch in Singapore. Confirm whether it already has development/demo data: do not automatically copy or erase it. Keep `dev` separate. Use an empty production database or a deliberately reviewed data migration; create the production owner via Clerk rather than copying users with dev Clerk IDs.

Obtain the migration owner's **direct** connection URL from main. Run migrations using a temporary terminal environment, keeping your development `.env` unchanged. Put the actual URL into environment variables locally; do not save it to code or a committed file. From `backend/`:

```powershell
# Paste the main DIRECT owner URL into the hidden prompt; it is not saved in shell history.
$migrationSecret = Read-Host 'Neon main DIRECT owner URL' -AsSecureString
$env:DATABASE_URL = [System.Net.NetworkCredential]::new('', $migrationSecret).Password
$env:DATABASE_URL_UNPOOLED = $env:DATABASE_URL
# APP_ENV=development is for the migration tool only.
$env:APP_ENV = 'development'
.\venv\Scripts\python.exe -m flask --app shopdesk db upgrade
.\venv\Scripts\python.exe -m core.apply_grants ..\scripts\security\database-roles.sql
```

Close this shell after migrations so owner credentials cannot be used accidentally. Do not start a running API in it. The role script creates `shopdesk_app` and `shopdesk_backup` if absent, grants business-table permissions, and excludes audit UPDATE and all DELETE/TRUNCATE. Re-run it after future migrations; the supplied migration workflow does that automatically.

Set separate role passwords with a password manager and `psql`'s `\password shopdesk_app` / `\password shopdesk_backup` (interactive, avoids SQL literals in query history). Create these restricted roles with the SQL script; do not use a role that belongs to an owner/neon_superuser group. Check in the Neon SQL editor as owner:

```sql
SELECT r.rolname, parent.rolname AS member_of
FROM pg_roles r JOIN pg_auth_members m ON m.member = r.oid
JOIN pg_roles parent ON parent.oid = m.roleid
WHERE r.rolname IN ('shopdesk_app', 'shopdesk_backup');
-- Expected: no rows.
SELECT has_table_privilege('shopdesk_app', 'public.audit_logs', 'SELECT') AS can_read,
       has_table_privilege('shopdesk_app', 'public.audit_logs', 'INSERT') AS can_append,
       has_table_privilege('shopdesk_app', 'public.audit_logs', 'UPDATE') AS can_update,
       has_table_privilege('shopdesk_app', 'public.audit_logs', 'DELETE') AS can_delete,
       has_table_privilege('shopdesk_app', 'public.audit_logs', 'TRUNCATE') AS can_truncate;
-- Expected: true, true, false, false, false.
```

Connect as `shopdesk_app` and test `BEGIN; DELETE FROM audit_logs WHERE false; ROLLBACK;`: expect permission denied even with zero target rows. Verify the immutable audit trigger exists. Keep runtime URLs **pooled**, role `shopdesk_app`, TLS `sslmode=require`. Backups use a **direct**, read-only `shopdesk_backup` URL; migrations alone use the direct owner URL. Password characters in URLs must be URL-encoded.

## 5. Cloudinary and Upstash

Copy a real Cloudinary connection URL from your account (`cloudinary://API_KEY:API_SECRET@CLOUD_NAME` with actual values), choose `CLOUDINARY_FOLDER=shopdesk/products`, and keep `MAX_UPLOAD_MB=4`. Do not expose the secret in any `VITE_` variable. Test a phone-image upload after deployment.

Create an Upstash Redis database near Singapore. Copy the **TLS Redis TCP** connection URL, e.g. `rediss://default:PASSWORD@HOST:6379`. This code uses redis-py/Flask-Limiter, so a REST endpoint or REST token is not a substitute. The API uses one Redis store, with distinct write buckets for admin and POS. Confirm the port in your dashboard. See [Upstash TLS security](https://upstash.com/docs/redis/features/security).

## 6. Import one Vercel project — Preview first

The Vercel services deployment has **not been deployed or verified remotely**. Local `vercel dev -L` routing has been verified; run this Preview check before production:

1. Review `feat/single-server` after local checks. The branch is pushed to GitHub for review. Import the repository **once**, project `shopdesk`, Root Directory **repo root** (leave blank or `.`). Use the services configuration in `vercel.json`, Node **22**; clear legacy project-level build/install/output overrides so each service owns its build. Do not set root to `backend` or `frontend/web`.
2. Keep root `vercel.json`: `backend` uses root `backend`, Flask entrypoint `wsgi:app`, Python 3.12 and pinned dependencies from `requirements.txt` through `pyproject.toml`. `frontend` uses root `frontend/web`, `npm ci --prefix ..` to install all workspace dependencies, `npm run build`, and output `dist`. Region remains `sin1`. Bare `/api` and `/api/` redirect to `/api/health`. Top-level `/api` and `/api/(.*)` rewrites target `backend`; the final catch-all targets `frontend`, whose own SPA fallback excludes assets and Vite development scripts. Service routing preserves the original `/api/...` path. Confirm logs build both services. See [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python) and [configuration reference](https://vercel.com/docs/project-configuration/vercel-json).
3. Set **Preview-only** variables with Neon **dev**, Clerk **dev** keys, dev webhook secret and Cloudinary dev folder. Use `APP_ENV=development`. Prefer a separate Preview TLS Redis database; never give Preview production secrets or main database URLs. Set `VITE_CLERK_PUBLISHABLE_KEY=pk_test_...` and matching backend Clerk key/PEM. Remove all legacy variables listed below.
4. Deploy the branch as Preview and record its exact HTTPS origin. Set `AUTHORIZED_PARTIES` to that origin; configure the same origin in the **development Clerk** instance. Redeploy so the function sees it. Use a stable branch Preview URL for future sign-ins; if you use a different URL, update both settings to that exact URL, without wildcard origins.
5. The checked-in web CSP supports Clerk development hosts. If your dev instance uses another host, generate an exact policy with `node scripts/security/configure-web-headers.mjs <preview-hostname> <dev-clerk-frontend-api-hostname>` in a reviewed Preview commit. Keep a production policy commit separate before promotion; it must match the live key.
6. For webhook testing, configure a **dev** endpoint `<preview-origin>/api/webhooks/clerk`, copy its signing secret into Preview, redeploy and test delivery. Do not repoint the production webhook.
7. From repo root run `.\scripts\smoke.ps1 -BaseUrl https://<preview-hostname>`. It checks SPA deep links, API health and anonymous auth/me rejection. Confirm `/assets/*` serves JavaScript/CSS, API errors return JSON with Flask headers, and API responses have no CORS permission headers. Sign in as dev admin and cashier: cashier `/admin` shows No access and downloads no admin chunk; test a sale, stock decrement, admin order visibility and `source=pos` audit row. Record results in progress-tracker.

There are no service bindings: the frontend is static and the browser calls public same-origin API paths. Bindings are only for runtime server-to-server calls; do not add a backend URL to Vite build variables. Both services are public only through the declared rewrites, and application role checks still protect API routes. See [Vercel services](https://vercel.com/docs/services), [routing](https://vercel.com/docs/services/routing) and [bindings](https://vercel.com/docs/services/bindings).

For **Production**, first complete Clerk DNS/live keys, restricted Neon roles, migration and backups above. Add `shop.example.com` in Vercel Domains and apply the DNS records shown. Review a CSP generated for the live Clerk hostname. Set these variables in **Production scope only**:

| Variable | Value |
|---|---|
| APP_ENV / LOG_LEVEL | production / INFO |
| DATABASE_URL | Neon main pooled URL, role shopdesk_app, TLS |
| CLERK_SECRET_KEY / CLERK_PUBLISHABLE_KEY | matching sk_live / pk_live keys |
| CLERK_JWT_KEY | production instance PEM, multiline or literal \n |
| CLERK_WEBHOOK_SIGNING_SECRET | production endpoint whsec signing secret |
| AUTHORIZED_PARTIES | https://shop.example.com (exact origin, no trailing slash) |
| VITE_CLERK_PUBLISHABLE_KEY | matching pk_live key, public build-time value |
| CLOUDINARY_URL / CLOUDINARY_FOLDER | real secret URL / shopdesk/products |
| RATELIMIT_STORAGE_URI | production Upstash TLS rediss URL |
| DB_ECHO / MAX_UPLOAD_MB | false / 4 |
| TZ_DISPLAY / CURRENCY | Asia/Kolkata / INR |
| SHOP_NAME, SHOP_ADDRESS, SHOP_PHONE, SHOP_GSTIN, RECEIPT_FOOTER | receipt details |

**Remove** `ADMIN_AUTHORIZED_PARTIES`, `POS_AUTHORIZED_PARTIES`, `ADMIN_CORS_ORIGINS`, `POS_CORS_ORIGINS`, `SHOPDESK_SERVER` and `VITE_API_BASE_URL` from every applicable environment. They cause startup/build errors. No API base URL is needed. Do not put owner `DATABASE_URL_UNPOOLED` or `TEST_DATABASE_URL` into the running project; migration/backup secrets belong in GitHub.

Vite embeds public values at build time, so changing the key requires a rebuild. Production builds reject test keys and a CSP that does not contain the exact live Clerk host and required security hosts. Production backend settings reject test keys, placeholders, non-TLS Redis, owner runtime credentials, missing DB TLS and non-exact/non-HTTPS origins.

Merge the reviewed branch only when ready to adopt the one-project layout. Configure Git integration's production branch deliberately; **CI does not automatically gate Vercel Git deployment**. For schema releases, run migrations before exposing code that needs the new schema, using expand/contract compatibility. This refactor has no migrations. Deploy/promote the reviewed commit yourself; the assistant has made no account or production changes.

## 7. GitHub production operations

Create a GitHub Environment named `production`. Configure its deployment branch restriction to `main`; add a required reviewer if your plan supports it. Add environment secrets:

- `NEON_MIGRATE_URL`: main DIRECT owner URL, using normal `postgresql://` syntax (normalized internally).
- `NEON_BACKUP_URL`: main DIRECT read-only `shopdesk_backup` URL, normal `postgresql://` syntax for pg_dump.

The supplied migration workflow runs after successful **push-to-main CI**, or manually via Actions → Production migrations → Run workflow. It checks out the tested commit and reapplies grants. First production setup is your manual step 4. Backups run at 18:00 UTC (23:30 IST); GitHub schedules can be delayed. Enable Actions notifications for failures. Run **Nightly backup** manually once and verify a nonempty downloadable artifact. Retention is 14 days; restrict who can download it. PostgreSQL 18's pg_dump is used; if Neon later upgrades beyond 18, upgrade the client first.

## 8. Smoke test and security sign-off

Run `scripts/smoke.ps1 -BaseUrl https://shop.example.com`. Then manually verify:

1. Owner can sign in to admin and billing. Cashier cannot access admin endpoints. Invite manager/cashier with the admin Users screen; confirm roles and webhook delivery.
2. Create a test product, upload a photo, make a test bill, toggle discount, confirm, and verify receipt, stock ledger and `order.confirm` audit row. Plan how to retain identifiable test records; do not delete audit evidence.
3. Both frontend HTTPS responses have CSP, HSTS and other headers. Open DevTools during sign-in, user menu, image preview and billing: no CSP-blocked requests. Run a headers scan on both web domains. Update CSP only for intended exact service hosts.
4. Verify rate limits in a controlled maintenance/test environment: writes 120/min, quotes 300/min, CSV 5/min, webhook 60/min. Confirm 429 includes Retry-After and requests to separate app instances share the quota via Redis. Do not flood production while cashiers are working.
5. Users → Sign out all devices requires confirmation and records `user.sessions_revoke`. Existing short-lived Clerk JWTs can remain usable until expiry; session revocation prevents refreshing them. For immediate account blocking, deactivate the account as well.
6. No demo accounts, test keys or placeholders in production; DEBUG/SQL echo off; errors show generic text and request ID. Check that backups and owner MFA are configured.

## 9. Restore drill (before real sales)

Neon's Free plan currently has up to a **6-hour** restore window, subject to plan/history limits; verify your project setting rather than assuming multi-day recovery. See [Neon restore history](https://neon.com/docs/introduction/history-window). Daily dumps can lose up to roughly a day's changes; increase backup frequency if the shop needs a smaller recovery gap.

Download the latest artifact into a private local directory. Create a **new isolated scratch Neon branch**, then create a **new empty database** (for example `shopdesk_restore_scratch`) in that branch. A normally cloned branch already contains objects/data; use the new empty database as the target. Never restore over main or the clone's populated database. Use a PostgreSQL client version compatible with the dump:

```powershell
# SCRATCH_RESTORE_URL is the new branch's DIRECT owner URL, not main/dev.
$restoreSecret = Read-Host 'Scratch branch DIRECT owner URL' -AsSecureString
$env:SCRATCH_RESTORE_URL = [System.Net.NetworkCredential]::new('', $restoreSecret).Password
& 'C:\Program Files\PostgreSQL\18\bin\pg_restore.exe' --dbname=$env:SCRATCH_RESTORE_URL --no-owner --no-acl --exit-on-error 'C:\PrivateBackups\shopdesk.dump'
```

The dump includes tables/triggers/data; do not migrate a baseline into the empty target first or objects will conflict. Reapply the reviewed role grants to the scratch database. Point a temporary local API at the **scratch** runtime URL, using the matching production Clerk settings and exact production authorized parties. Use an authorized **admin** token to call `GET /api/admin/stock/verify`; expect every ledger and product quantity to match. For a local terminal request, obtain a fresh short-lived token from your signed-in production admin session and enter it into a hidden prompt; do not change production allowed origins or paste the token into files. Supply it as a Bearer header to the local scratch API. Check a few orders, audit rows, pricing settings, and Cloudinary public IDs. Keep branch access restricted because restored data is real customer data. Record dump time, drill date, scratch branch and database, result and recovery duration in progress-tracker. An isolated drill has not been performed by the coding assistant.

## 10. Rollback and rotate secrets

For code rollback, select a known-good Vercel deployment and use **Instant Rollback / Promote to Production**. Roll back the single project to its known-good deployment. Do not automatically downgrade the database; additive migrations let old code coexist. For corrupt data, pause writes, restore to a new branch, validate stock/records, then deliberately switch runtime URLs and redeploy. Keep main untouched until recovery is verified.

Rotation procedure:

- Clerk secret: create/rotate via Clerk dashboard, update the project Production environment, redeploy/test user operations, then revoke the old secret. A JWT signing-key rotation also requires the matching new `CLERK_JWT_KEY`; test both API areas and session refresh. Rotate webhook signing secret with the endpoint and project environment together.
- Cloudinary: issue a new credential in Cloudinary, update the project Cloudinary URL, redeploy, verify upload/CDN, then revoke the old credential. Preserve public IDs/folder.
- Neon: rotate app and backup role passwords separately. Update the runtime pooled URL / GitHub backup secret, redeploy and test. Rotate the owner only in the migration secret and password manager. Keep TLS query parameters and URL-encode passwords.
- Redis: rotate the database password, update the `RATELIMIT_STORAGE_URI` value, redeploy and check quotas. Do not switch production to memory to get around a Redis outage.
- Staff credentials shared during development: change through Clerk before reuse; do not publish them or reuse them as production passwords.

Keep secret values in your password manager and encrypted service settings. Never paste them into issues, screenshots, commit messages or this guide.

### Local services validation on Windows

CLI 62.2.0 misquoted the installed uv path under a Windows user directory containing spaces. Local verification used a copy of `uv.exe` in ignored `.tools/uv`, with that directory and `backend/venv/Scripts` prepended to PATH. This is a local workaround, not a cloud requirement. Start `npx vercel@latest dev -L --listen 127.0.0.1:5180` and run the smoke script against that origin. Sign-in additionally needs that exact origin in development Clerk and `AUTHORIZED_PARTIES`; anonymous routing checks do not change those settings.
