# Manual deployment — ShopDesk

Prepared 2026-10-05. You carry out the account changes and deployment yourself. This guide matches the repository's two Flask APIs, two Vite apps, Neon, Clerk, Cloudinary and Upstash. Keep your existing development `.env` on Neon **dev**.

## 1. Decide the production addresses

Replace `example.com` everywhere with your domain:

| Component | Project | Root directory | Address |
|---|---|---|---|
| Admin web | shopdesk-admin-web | frontend/admin-web | https://admin.example.com |
| Billing web | shopdesk-pos-web | frontend/pos-web | https://pos.example.com |
| Admin API | shopdesk-admin-api | backend | https://admin-api.example.com |
| Billing API | shopdesk-pos-api | backend | https://pos-api.example.com |

Use Vercel Pro before taking real shop orders; Hobby is for personal/non-commercial projects. Verify current terms on [Vercel pricing](https://vercel.com/pricing). Use a **private GitHub repository** for the supplied backup workflow: database artifacts contain customer information. The workflow refuses a public repository. If the code must remain public, move backups to a separate private repository/storage and adapt that workflow first.

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
npm run build
npm audit --omit=dev --audit-level=high
```

Review your diff; commit and push it yourself. Enable branch protection requiring CI. Install the existing pre-commit hooks with `backend\venv\Scripts\pre-commit.exe install` from the repository root. CI scans full Git history with gitleaks and audits dependencies. A failed secret scan requires rotating the exposed credential before addressing the history.

## 3. Create Clerk production authentication

In Clerk, create/select a **production instance**, connect your domain, and add exactly the DNS records Clerk displays. Wait for verification. Configure:

- Access mode **Invite-only**; use username/password as in development.
- Session custom claim: `"metadata": "{{user.public_metadata}}"`.
- Frontend origins: only `https://admin.example.com` and `https://pos.example.com`.
- Session maximum lifetime: approximately one shift (for example 8 hours). Set inactivity timeout if your plan supports it; confirm the actual dashboard controls available.
- Create a fresh owner account with public metadata `{"role":"admin"}`. Use a strong password and enable MFA where available. Development demo accounts/passwords must not be copied into production.

Save the **live** publishable key (`pk_live_...`), live secret key (`sk_live_...`), PEM JWT verification public key, and Frontend API hostname. Use the public key belonging to this production instance, not the dev key. Create a webhook targeting `https://admin-api.example.com/api/webhooks/clerk`, subscribing to user.created/user.updated/user.deleted. Save its `whsec_...` signing secret; test delivery after the API is live.

Generate the web CSP for your actual domain and the Clerk Frontend API hostname (hostnames only):

```powershell
Set-Location E:\Personal-Projects\ShopDesk
node scripts/security/configure-web-headers.mjs example.com clerk.example.com
```

This overwrites **both web apps'** `vercel.json` with exact API/auth hosts and security headers. Review and commit the result before importing/deploying the web apps. Checked-in development policies are not your production policy. The generator includes Clerk's current fraud protection hosts and Cloudflare challenges; see [Clerk CSP documentation](https://clerk.com/docs/guides/secure/best-practices/csp-headers). Do not add broad `https:` or script `unsafe-inline` to silence errors; identify the blocked host first.

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
.\venv\Scripts\python.exe -m flask --app admin_api db upgrade
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

Create an Upstash Redis database near Singapore. Copy the **TLS Redis TCP** connection URL, e.g. `rediss://default:PASSWORD@HOST:6379`. This code uses redis-py/Flask-Limiter, so a REST endpoint or REST token is not a substitute. Both APIs use the same Redis store, with server-specific namespaces. Confirm the port in your dashboard. See [Upstash TLS security](https://upstash.com/docs/redis/features/security).

## 6. Import the four Vercel projects

Import the GitHub repository four times using the table in step 1. Add the corresponding custom domain in each project's Domains settings, and create the DNS records Vercel displays. Wait for HTTPS issuance.

For both web projects: Vite preset; Node 22; enable **Include source files outside the Root Directory in the Build Step**, because `frontend/packages/shared` and the workspace lockfile are outside each app. Install using the frontend workspace root (`cd .. && npm ci` if the install starts inside the app folder); build `npm run build`; output `dist`. If Vercel auto-detects/install-resolves the workspace, retain that equivalent root install. Confirm build logs include the shared package. [Vercel monorepo guidance](https://vercel.com/docs/monorepos/monorepo-faq).

For both API projects: root `backend`; Python runtime; existing `api/index.py` entry and `vercel.json`; function region `sin1`. `backend/.python-version` pins Python 3.12. Vercel installs `requirements.txt`; do not use `flask run` as a production start command. [Python runtime documentation](https://vercel.com/docs/functions/runtimes/python).

Set the following variables in the **Production** environment only, then redeploy. Never give Preview production secrets. If you need dev previews, use a separate reviewed dev configuration and exact origins; random preview sign-in is deliberately not enabled by production settings.

| Variable | Admin API | POS API |
|---|---|---|
| SHOPDESK_SERVER | admin | pos |
| APP_ENV | production | production |
| LOG_LEVEL | INFO | INFO |
| DATABASE_URL | pooled main, shopdesk_app | same runtime URL |
| CLERK_SECRET_KEY | production sk_live key | production sk_live key |
| CLERK_PUBLISHABLE_KEY | production pk_live key | production pk_live key |
| CLERK_JWT_KEY | production PEM public key | same public key |
| CLERK_WEBHOOK_SIGNING_SECRET | production whsec signing secret | optional (no webhook route) |
| ADMIN_CORS_ORIGINS | https://admin.example.com | same |
| ADMIN_AUTHORIZED_PARTIES | https://admin.example.com | same |
| POS_CORS_ORIGINS | https://pos.example.com | same |
| POS_AUTHORIZED_PARTIES | https://pos.example.com | same |
| CLOUDINARY_URL | real secret URL | real URL (current shared configuration requires it) |
| CLOUDINARY_FOLDER | shopdesk/products | shopdesk/products |
| RATELIMIT_STORAGE_URI | TLS Upstash rediss URL | same Redis URL |
| DB_ECHO | false | false |
| MAX_UPLOAD_MB | 4 | 4 (POS request cap remains 256 KB) |
| SHOP_NAME, SHOP_ADDRESS, SHOP_PHONE | real shop details | same receipt details |
| TZ_DISPLAY / CURRENCY | Asia/Kolkata / INR | same |

Do not put owner `DATABASE_URL_UNPOOLED` or test database credentials into running API projects. Migration/backup URLs belong in GitHub only. Put PEM as real multiline text or literal `\n`; settings accept both.

Web variables, also Production-only:

| Variable | Admin web | POS web |
|---|---|---|
| VITE_CLERK_PUBLISHABLE_KEY | pk_live production key | same key |
| VITE_API_BASE_URL | https://admin-api.example.com | https://pos-api.example.com |

Vite embeds these values **at build time**; changing them requires a rebuild. Local `.env.development` must not supply test keys to a production build. Production Vercel builds now stop if the key is not live, the API URL is not HTTPS, or CSP does not contain the exact production API and Clerk hosts.

Deploy APIs first after migrations, then frontends. During future schema changes use expand/contract migrations. Vercel Git auto-deploy can finish before GitHub migrations; for changes that require a new table before startup, hold/manual-trigger application deployment until migrations succeed. CI completion alone does not gate Vercel auto-deploy.

## 7. GitHub production operations

Create a GitHub Environment named `production`. Configure its deployment branch restriction to `main`; add a required reviewer if your plan supports it. Add environment secrets:

- `NEON_MIGRATE_URL`: main DIRECT owner URL, using normal `postgresql://` syntax (normalized internally).
- `NEON_BACKUP_URL`: main DIRECT read-only `shopdesk_backup` URL, normal `postgresql://` syntax for pg_dump.

The supplied migration workflow runs after successful **push-to-main CI**, or manually via Actions → Production migrations → Run workflow. It checks out the tested commit and reapplies grants. First production setup is your manual step 4. Backups run at 18:00 UTC (23:30 IST); GitHub schedules can be delayed. Enable Actions notifications for failures. Run **Nightly backup** manually once and verify a nonempty downloadable artifact. Retention is 14 days; restrict who can download it. PostgreSQL 18's pg_dump is used; if Neon later upgrades beyond 18, upgrade the client first.

## 8. Smoke test and security sign-off

Run `scripts/smoke.ps1 -Domain example.com`. Then manually verify:

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

The dump includes tables/triggers/data; do not migrate a baseline into the empty target first or objects will conflict. Reapply the reviewed role grants to the scratch database. Point a temporary local API at the **scratch** runtime URL, using the matching production Clerk settings and exact production authorized parties. Use an authorized **admin** token to call `GET /api/stock/verify`; expect every ledger and product quantity to match. For a local terminal request, obtain a fresh short-lived token from your signed-in production admin session and enter it into a hidden prompt; do not change production allowed origins or paste the token into files. Supply it as a Bearer header to the local scratch API. Check a few orders, audit rows, pricing settings, and Cloudinary public IDs. Keep branch access restricted because restored data is real customer data. Record dump time, drill date, scratch branch and database, result and recovery duration in progress-tracker. An isolated drill has not been performed by the coding assistant.

## 10. Rollback and rotate secrets

For code rollback, select a known-good Vercel deployment and use **Instant Rollback / Promote to Production**. Roll back both affected APIs/frontends as appropriate. Do not automatically downgrade the database; additive migrations let old code coexist. For corrupt data, pause writes, restore to a new branch, validate stock/records, then deliberately switch runtime URLs and redeploy. Keep main untouched until recovery is verified.

Rotation procedure:

- Clerk secret: create/rotate via Clerk dashboard, update both API Production environments, redeploy/test user operations, then revoke the old secret. A JWT signing-key rotation also requires the matching new `CLERK_JWT_KEY`; test both APIs and session refresh. Rotate webhook signing secret with the endpoint and admin environment together.
- Cloudinary: issue a new credential in Cloudinary, update both API URLs, redeploy, verify upload/CDN, then revoke the old credential. Preserve public IDs/folder.
- Neon: rotate app and backup role passwords separately. Update both runtime pooled URLs / GitHub backup secret, redeploy and test. Rotate the owner only in the migration secret and password manager. Keep TLS query parameters and URL-encode passwords.
- Redis: rotate the database password, update both `RATELIMIT_STORAGE_URI` values, redeploy and check quotas. Do not switch production to memory to get around a Redis outage.
- Staff credentials shared during development: change through Clerk before reuse; do not publish them or reuse them as production passwords.

Keep secret values in your password manager and encrypted service settings. Never paste them into issues, screenshots, commit messages or this guide.
