# Spec 09 — Security Hardening

**Status:** 🟨 Code built · production setup and release sign-off pending owner · **Depends on:** 01–08 · **Server(s):** both

## 1. Goal
Close the remaining gaps before real money and real customer names go into the system. Much of security is already built in: server-side pricing, Clerk auth with `azp` + role checks, and the append-only audit log. This spec checks it, adds defence in depth on the free cloud stack, and sets up backups.

## 2. Threat model (short)
| Threat | Example | Mitigation (where) |
|---|---|---|
| Price tampering | Cashier edits the request to sell at ₹1 | Server computes prices (BR-5, spec 06/07) |
| Privilege escalation | Cashier calls the admin API with their token | `azp` check per server + role check + no admin routes on pos_api (spec 02) |
| Account takeover / brute force | Guessing passwords | Clerk: password rules, attempt limits, bot protection. MFA for admins if the plan allows |
| Leaked Clerk secret key | Attacker creates an admin user | Secret only in Vercel env (Production scope) + password manager. Rotate in Clerk if exposed. gitleaks hook |
| Production secrets leaking into previews | A preview build reads live keys | Vercel env vars scoped to **Production** only. Preview gets dev values or nothing (spec 10) |
| Overselling / race | Two counters, last unit | Row locks + CHECK (spec 07) |
| Covering tracks | Staff deletes evidence | Append-only audit + trigger + restricted DB role (spec 05, here) |
| XSS | Product name `<script>` | React escaping, no `dangerouslySetInnerHTML`, CSP (here) |
| CSRF | Malicious page posts to the API | Bearer tokens, not cookies. CORS allow-list |
| Forged webhooks | Fake `user.updated` to grant admin | svix signature verification + dedupe (spec 02) |
| Malicious upload | Polyglot image / huge file | Pillow verify + re-encode + size cap before Cloudinary (spec 03) |
| SQL injection | Search box | ORM parameterisation |
| CSV/formula injection | `=HYPERLINK(...)` in export | Escape leading `= + - @` (spec 05/08) |
| Data loss | Bad migration, accidental delete | Neon point-in-time restore + nightly `pg_dump` artifact + restore drill |

## 3. Tasks
- [ ] 1. **Security headers** via the `headers` section of each web app's `vercel.json` (spec 10 §3.5), and Flask `after_request` on the APIs for JSON responses. CSP value:
```
default-src 'self'; script-src 'self' https://clerk.<domain> https://challenges.cloudflare.com; connect-src 'self' https://<app>-api.<domain> https://clerk.<domain>; img-src 'self' data: blob: https://img.clerk.com https://res.cloudinary.com; style-src 'self' 'unsafe-inline'; frame-src https://challenges.cloudflare.com; worker-src 'self' blob:; frame-ancestors 'none'
```
  plus `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`, and `Strict-Transport-Security: max-age=31536000; includeSubDomains`. (`blob:` in img-src lets the browser preview the resized image before upload. `challenges.cloudflare.com` is Clerk's bot-protection widget.) Check Clerk's current CSP documentation for the exact domains, then test sign-in with the browser console open (no CSP violations).
- [x] 2. **API rate limits** (Flask-Limiter, keyed by Clerk user id, falling back to IP): writes 120/min, quote 300/min, CSV export 5/min, webhook 60/min. 429 with `Retry-After`. Production storage = **Upstash Redis** (`RATELIMIT_STORAGE_URI=rediss://…`), because serverless instances don't share memory. Optionally add a Vercel Firewall rate-limit rule on `/api/*` as an outer layer.
- [ ] 3. **Neon DB roles (prod):** `neondb_owner` (default, migrations only, used only by the GitHub Actions secret `NEON_MIGRATE_URL`, never by the running apps), `shopdesk_app` (runtime: SELECT/INSERT/UPDATE on business tables, **SELECT + INSERT only** on `audit_logs`, no DELETE/TRUNCATE anywhere), `shopdesk_backup` (read-only, for `pg_dump`). Both APIs' `DATABASE_URL` uses `shopdesk_app` on the pooled host.
- [x] 4. **Request limits:** `MAX_CONTENT_LENGTH` 4 MB (admin, under Vercel's ~4.5 MB function body limit), 256 KB (POS). Pydantic limits on strings and lists.
- [ ] 5. **Session safety:** set the Clerk session lifetime (and inactivity timeout if your plan has it) to about one shift. A "Sign out all devices" button in the Users page for a user (revoke sessions via the Clerk API).
- [x] 6. **Secrets:** gitleaks pre-commit + CI step. In production, config refuses `sk_test_` keys, placeholder values and a missing `CLERK_JWT_KEY`. Write down a rotation procedure (Clerk secret key, Cloudinary API secret, Neon role passwords) in SETUP_GUIDE.
- [x] 7. **Dependency audit:** `pip-audit` + `npm audit --omit=dev` in CI. Fix highs before release. Turn on Dependabot.
- [ ] 8. **Backups:** (a) Neon's built-in point-in-time restore. Note the free-tier history window in SETUP_GUIDE. (b) GitHub Actions `backup.yml` nightly `pg_dump -Fc` with the `shopdesk_backup` role → artifact, 14-day retention (spec 10). (c) Images: Cloudinary keeps them, and the DB holds the public IDs. Optional monthly export.
- [ ] 9. **Restore drill:** restore the latest dump into a new Neon branch (`pg_restore --no-owner`), point a local API at it, and run `/api/stock/verify`. Record the date in progress-tracker.
- [x] 10. **Error hygiene:** prod `DEBUG=False`, generic 500 with request ID, traces only in Vercel function logs (short retention on Hobby. The audit log is the durable record). Never log `Authorization` headers or webhook bodies containing PII beyond what's needed.
- [x] 11. **Security test pass:** route-role meta-test, `azp` mismatch test, webhook signature tests, the "no cost in POS" tests, the audit meta-test, upload fuzz, and an XSS render test.
- [ ] 12. **Review checklist** (below) completed and signed off in progress-tracker.

## 4. Release security checklist
- [ ] All endpoints have `@require_role` or are on the public allowlist (test green)
- [ ] Each API rejects tokens from the other app (`azp` test green)
- [ ] Clerk production: Access mode **Invite-only**, `metadata` session claim set, allowed origins = only the two production frontends
- [ ] No `sk_test_` / `pk_test_` keys in production settings
- [ ] No float in money paths
- [ ] POS API responses contain no cost/profit fields
- [ ] Audit trigger present in the Neon `main` branch. `shopdesk_app` can't UPDATE/DELETE `audit_logs`
- [ ] HTTPS everywhere, HSTS + CSP headers present, with no CSP errors during sign-in
- [ ] Owner account has a strong password (+ MFA if available). No test users in production
- [ ] Nightly backup artifact present. Last restore drill date recorded
- [ ] `pip-audit` / `npm audit` clean of high/critical. gitleaks clean
- [ ] `.env` never committed (check `git log --all -- .env`)

## 5. Acceptance criteria
- [ ] Every item in §4 is ticked.
- [ ] A headers scan (e.g. securityheaders.com) of both frontends shows the task 1 headers.
- [ ] Connected as `shopdesk_app`, `DELETE FROM audit_logs` → permission denied.
- [ ] The nightly backup exists, and the restore drill into a Neon branch passes `/api/stock/verify`.

## Implementation and remaining manual checks — 2026-10-05

- Code: API/web security headers; production CSP generator plus build-time exact-host/live-key guard; Redis rate limits with isolated buckets, authenticated subject/IP fallback, 429/Retry-After; current body limits; audited admin session revocation including failure; strict production HTTPS/TLS/role/Redis/key validation; safe Cloudinary error logging; upload pixel cap/fuzz and XSS regression tests.
- Prepared: scripts/security/database-roles.sql, migration/grant helper, nightly private-repository backup workflow (14 days), Dependabot and full-history gitleaks/dependency-audit CI.
- Tasks 1/3/5/8/9/12 retain unchecked status because final production CSP sign-in verification, actual Neon grants, Clerk production session settings, successful backup artifact/restore drill and owner sign-off require the owner's deployment. The supporting code/scripts are ready. [Manual deployment guide](../../MANUAL_DEPLOYMENT.md) lists each action in order.
- Existing short-lived JWTs expire normally after session revocation. Deactivation additionally blocks the local mirror immediately. Redis errors fail closed; there is no production memory fallback.
- Local dependency audits returned zero known vulnerabilities. Gitleaks full-history scan clean after documenting one exact false-positive fingerprint for a mocked PUBLIC Clerk publishable key; no real credential was excluded.
- No production infrastructure was altered or deployed. SQL roles/grants and live backups remain unexecuted. Keep the release checklist and acceptance criteria unchecked until evidence exists.
