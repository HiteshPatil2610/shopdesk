# Spec 10 — Deployment (single Vercel project)

**Status:** Guide/configuration prepared; remote Preview and production acceptance pending owner. **Depends on:** 01–09 and approved spec 11.

## 1. Goal

One repo-root Vercel project `shopdesk` serves `https://shop.<domain>`: static Vite web, `/admin` and `/pos` SPA routes, same-origin `/api/*` Python Flask function. Neon main, Clerk live instance, Cloudinary and TLS Redis are production services. Preview uses Neon dev and Clerk dev keys only. Spec 11 supersedes the original four-project deployment design.

## 2. Deploy pipeline

GitHub CI validates backend/frontend, full-history secrets and dependency audits. After successful push-to-main CI, the production migration workflow runs `flask --app shopdesk db upgrade` with a direct owner connection and reapplies restricted grants. Vercel Git builds/deploys the one project independently; CI completion does not gate its deployment. All schema changes require expand/contract compatibility. This refactor changes no schema. Nightly backups use the unchanged workflow, a private repository and direct read-only credentials.

## 3. Owner tasks

Follow [MANUAL_DEPLOYMENT.md](../../MANUAL_DEPLOYMENT.md) in order; it contains exact commands, env scopes, role checks, Preview smoke, DNS, backup/restore and rotation steps.

- [ ] Review/push the branch and require CI before merge.
- [ ] Import one project with Root Directory repo root; verify static + Python build on Preview.
- [ ] Preview: dev DB/keys, exact AUTHORIZED_PARTIES, dev Clerk allowed origin/webhook; execute smoke and staff flows.
- [ ] Decide app domain; verify Clerk production DNS and invite-only/session claims.
- [ ] Migrate main deliberately with owner credentials; establish shopdesk_app and shopdesk_backup grants and immutable audit trigger.
- [ ] Set Production-only runtime/live values and public build key; generate exact live Clerk CSP in root vercel.json.
- [ ] Configure TLS Redis and production Cloudinary; test quotas and uploads.
- [ ] Configure production Clerk origin https://shop.<domain> and webhook https://shop.<domain>/api/webhooks/clerk.
- [ ] Configure GitHub production Environment reviewers/branch restrictions and migration/backup secrets.
- [ ] Deploy/promote the reviewed commit; verify HTTPS, deep links, role denial, no-cost responses, signed webhook and session revocation.
- [ ] Run/download backup; restore into an isolated empty scratch DB and verify stock ledger and orders.
- [ ] Record the deployment URL, tested commit, checks and recovery duration in progress-tracker.

## 4. Acceptance and rollback

Production readiness requires every owner task above, the spec 09 sign-off and a successful restore drill. No remote deployment or account settings change was performed by the coding assistant. Use Vercel rollback for the single app; do not downgrade/drop production schema automatically. Restored data is validated on a new branch before deliberately changing runtime URLs. Current service terms and plan allowances must be checked before commercial use.
