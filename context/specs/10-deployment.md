# Spec 10 — Deployment (Vercel)

**Status:** ⬜ Not started · **Depends on:** 01–09 · **Server(s):** both

**Owner handoff (2026-10-05):** Deployment will be performed manually by the owner.
Follow [MANUAL_DEPLOYMENT.md](../../MANUAL_DEPLOYMENT.md) for the current step-by-step
process, exact production environment values, headers generator, restricted role script,
backup/migration workflows, smoke test, rotation and restore drill. Supporting files are
prepared; production deployment and acceptance checks are not yet executed.

## 1. Goal
ShopDesk runs on the internet, deployed automatically from GitHub to **Vercel**:

| Piece | Vercel project | Root Directory | URL |
|---|---|---|---|
| admin-web | `shopdesk-admin-web` | `frontend/admin-web` | `https://admin.<domain>` |
| pos-web | `shopdesk-pos-web` | `frontend/pos-web` | `https://pos.<domain>` |
| admin_api | `shopdesk-admin-api` | `backend` (`SHOPDESK_SERVER=admin`) | `https://admin-api.<domain>` |
| pos_api | `shopdesk-pos-api` | `backend` (`SHOPDESK_SERVER=pos`) | `https://pos-api.<domain>` |
| Database | Neon project `shopdesk`, branch `main` | — | — |
| Auth | Clerk production instance | — | `clerk.<domain>` / `accounts.<domain>` |
| Images | Cloudinary, folder `shopdesk/products` | — | `res.cloudinary.com/...` |
| Rate-limit store | Upstash Redis (Vercel Marketplace, free) | — | — |
| CI, migrations, backups | GitHub Actions | — | — |

> ⚠️ **Plan:** Vercel **Hobby** (free) is for personal, non-commercial use. Use it while building and testing. **Before the shop takes real orders, upgrade the Vercel team to Pro.** Everything else in this spec stays the same.

## 2. Deploy pipeline
```
git push main
  ├─► GitHub Actions ci.yml ── lint + tests ──► (green) ──► migrate.yml: flask db upgrade on Neon main
  └─► Vercel Git integration builds & deploys all 4 projects (each only if its folder changed)
nightly 23:30 IST ─► GitHub Actions backup.yml: pg_dump Neon main → artifact (14-day retention)
```
**The migration rule (ADR A13):** because Vercel may finish deploying before or after `migrate.yml` runs, every migration must work with both the old and the new code:
1. **Expand:** add new columns/tables (nullable or with defaults). Deploy.
2. Code starts using them. Deploy.
3. **Contract:** drop old columns in a *later* release.

Never rename or drop a column in the same release that stops using it.

## 3. Tasks

### 3.1 Domain
- [ ] 1. Buy a domain. DNS can stay at the registrar, or move to Vercel DNS or Cloudflare DNS (all free). You'll add records for the 4 Vercel subdomains and for Clerk.

### 3.2 Neon (production database)
- [ ] 2. Branch **`main`** = production (region Singapore). Branch **`dev`** = development.
- [ ] 3. First migration on `main`, once from your machine with `main`'s **direct** URL. After that, `migrate.yml` keeps it up to date.
- [ ] 4. (Spec 09) Create the `shopdesk_app` (runtime) and `shopdesk_backup` (read-only) roles. Both API projects use `shopdesk_app` on the **pooled** host.
> Optional: the **Neon integration in the Vercel Marketplace** can inject `DATABASE_URL` automatically and create a Neon branch for each preview deployment. It uses the owner role, so if you use it, override `DATABASE_URL` for Production with the `shopdesk_app` URL. `core/config.py` already accepts the `postgresql://` prefix it injects.

### 3.3 Backend entry for Vercel
- [ ] 5. Add `backend/api/index.py` and `backend/vercel.json` exactly as in architecture §3. Pin the Python version Vercel should use (a `.python-version` file containing `3.12` in `backend/`, or the project setting, whichever Vercel's current Python docs prefer). Keep `requirements.txt` in `backend/`. Vercel installs it.
- [ ] 6. Keep the cold start lean: no heavy work at import time. Create the DB engine lazily, and create the Cloudinary/Clerk clients on first use.
- [ ] 7. `GET /api/health` must not require auth and must stay cheap. It's used for pre-warming.

### 3.4 Create the 4 Vercel projects
- [ ] 8. Sign in to Vercel with GitHub → **Add New → Project** → import `HiteshPatil2610/shopdesk` **four times**, once per row:

| Setting | admin-web | pos-web | admin-api | pos-api |
|---|---|---|---|---|
| Project name | `shopdesk-admin-web` | `shopdesk-pos-web` | `shopdesk-admin-api` | `shopdesk-pos-api` |
| Root Directory | `frontend/admin-web` | `frontend/pos-web` | `backend` | `backend` |
| Framework preset | Vite | Vite | Other (Python detected) | Other (Python detected) |
| Build / output | default (`npm run build` → `dist`) | default | — | — |
| Env (Production) | `VITE_CLERK_PUBLISHABLE_KEY=pk_live_…`, `VITE_API_BASE_URL=https://admin-api.<domain>` | `VITE_CLERK_PUBLISHABLE_KEY=pk_live_…`, `VITE_API_BASE_URL=https://pos-api.<domain>` | see SETUP_GUIDE §11 | see SETUP_GUIDE §11 |
| Custom domain | `admin.<domain>` | `pos.<domain>` | `admin-api.<domain>` | `pos-api.<domain>` |

- [ ] 9. In each project → Settings → Git → **Ignored Build Step**, skip builds when the project's folder (and `frontend/packages/shared` for the web apps) didn't change, so a docs-only commit doesn't rebuild all 4.
- [ ] 10. In the API projects, set the function region to **Singapore (`sin1`)** (also in `vercel.json`).
- [ ] 11. **Preview deployments** (v1): Vercel builds a preview for every non-`main` push. Previews get random URLs, so they don't match the exact `*_AUTHORIZED_PARTIES` origins and sign-in won't work on them. That's fine for v1: use them only to check that the build passes. **Never give the Preview environment production secrets.** Give Preview the Neon `dev` + Clerk dev values, or nothing. A proper staging setup is in §5.

### 3.5 Frontend `vercel.json` (each web app)
- [ ] 12. SPA routing + security headers (spec 09 task 1):
```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }],
  "headers": [
    { "source": "/(.*)", "headers": [
      { "key": "X-Content-Type-Options", "value": "nosniff" },
      { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
      { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" },
      { "key": "Strict-Transport-Security", "value": "max-age=31536000; includeSubDomains" },
      { "key": "Content-Security-Policy", "value": "<from spec 09 task 1>" }
    ]}
  ]
}
```
(Vercel serves real files such as `/assets/*.js` before applying the rewrite, so only unknown routes fall back to `index.html`.)

### 3.6 Clerk production instance
- [ ] 13. Clerk dashboard → create the **Production** instance → domain `<domain>` → add the DNS records Clerk lists. Wait for them to verify.
- [ ] 14. Repeat the spec 02 §5 configuration: Access mode **Invite-only**, username + password, custom session claims, allowed origins `https://admin.<domain>` + `https://pos.<domain>`.
- [ ] 15. Webhook → `https://admin-api.<domain>/api/webhooks/clerk` → copy the signing secret into `shopdesk-admin-api` env.
- [ ] 16. Create the owner user in the production dashboard with public metadata `{"role":"admin"}` (or run `promote-admin` locally against production with care) → sign in.

### 3.7 Upstash Redis (rate limits)
- [ ] 17. Vercel → Storage / Marketplace → **Upstash Redis** (free) → connect it to both API projects. Set `RATELIMIT_STORAGE_URI` to its `rediss://…` URL. Local dev keeps `memory://`.

### 3.8 GitHub Actions
- [ ] 18. `ci.yml`: Python 3.12 + `services: postgres:16` + ruff/black/pytest, and Node 22 + lint/typecheck/test/build. Runs on push and PR.
- [ ] 19. `migrate.yml`: `on: workflow_run` of `ci.yml` (completed, success, branch `main`) → `pip install -r backend/requirements.txt` → `flask --app admin_api db upgrade` with secret `NEON_MIGRATE_URL` (`main`, **direct**, owner role). Use `concurrency: migrate` so two runs never overlap.
- [ ] 20. `backup.yml`: nightly cron `0 18 * * *` (23:30 IST) → `pg_dump -Fc "$NEON_BACKUP_URL"` (client version ≥ Neon's) → upload artifact, `retention-days: 14`.
- [ ] 21. Repo secrets: `NEON_MIGRATE_URL`, `NEON_BACKUP_URL`. Nothing else, because Vercel holds the app secrets.

### 3.9 Smoke test and docs
- [ ] 22. `scripts/smoke.ps1 <base-domain>`: both `/api/health` return 200, `/api/auth/me` without a token returns 401, both frontends return 200, and a deep link (`/products`) on admin-web returns 200 (SPA rewrite works).
- [ ] 23. Add "Deploy & operate" to SETUP_GUIDE: deploy, **roll back** (Vercel → Deployments → previous → *Promote to Production*/*Instant Rollback*), restore (Neon point-in-time restore to a new branch, or `pg_restore` from the artifact), and rotate secrets.

## 4. Acceptance criteria
- [ ] Pushing to `main` deploys the changed projects automatically. Migrations run only after CI passes.
- [ ] All 4 custom domains serve over HTTPS. Sign-in works with the Clerk **production** instance.
- [ ] A full sale works in production: cashier signs in → bill → discount → confirm → admin sees reduced stock + the `order.confirm` audit row.
- [ ] Image upload works (a large phone photo is resized in the browser and stays under the 4.5 MB limit). The image is served from `res.cloudinary.com`.
- [ ] After 30+ minutes idle, the first billing action completes within ~3 s (cold start), with no ~1-minute wait.
- [ ] Rate limits hold across instances (Upstash): hammering `/api/cart/quote` eventually returns 429.
- [ ] A migration that adds a column deploys cleanly, with no errors from the old or new code while it rolls out.
- [ ] The nightly backup artifact appears. A test restore into a scratch Neon branch passes `/api/stock/verify`.
- [ ] No secret exists in the repo. Production secrets exist only in Vercel, GitHub secrets and your password manager.
- [ ] Before real sales: the Vercel team is on **Pro**.

## 5. Upgrade path
| Need | Fix |
|---|---|
| Commercial use (required for the live shop) | Vercel Pro |
| DB > free storage or compute | Neon paid plan |
| More images/bandwidth | Cloudinary paid plan |
| Staging environment | A `staging` git branch + Neon `staging` branch + Preview env vars scoped to that branch |

## 6. Open questions
- Domain name?
- When will the Vercel team move to Pro (before go-live)?
- Thermal printer model (browser print at 80mm works for most)?
