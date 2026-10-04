# Spec 02 — Authentication & Roles (Clerk)

**Status:** 🟨 Built, waiting for the owner's manual sign-in test (task 10) · **Depends on:** 01 · **Server(s):** both

## 1. Goal
Only staff accounts the admin has created can use either server. Sign-in, passwords and sessions are handled by **Clerk**. ShopDesk handles **roles** and **which server each role may use**, and keeps a local `users` mirror so every order, product edit and audit row points to a real person.

## 2. User stories
- As the **owner**, I set myself up as admin once, then create staff accounts (username + password) from the ShopDesk Users page.
- As a **cashier**, I sign in on the Billing Counter with my username and password and stay signed in for my shift.
- As a **cashier**, I can't use the Admin Console, even if I open its URL and sign in.
- As the **owner**, when I deactivate (ban) a user, they lose access within about a minute.

## 3. Scope
**In:** Clerk app configuration, the frontend Clerk integration (`@clerk/react`), backend JWT verification, `azp` + role checks, the local `users` mirror (just-in-time sync + webhooks), user management through the Clerk Backend API, a `promote-admin` CLI, and audit events for auth and users.
**Out:** custom-built password storage or login forms, SSO/social login (can be switched on in Clerk later), multiple shops (Clerk Organizations, later).

## 4. Business rules touched
BR-8. New:
- **AU-1** No self-registration. Clerk **Access mode = Invite-only** (API value `restricted`; formerly called "Restricted" sign-up mode).
- **AU-2** Role is stored in Clerk `public_metadata.role` ∈ {`admin`, `manager`, `cashier`}. A user with no valid role → 403 on both servers.
- **AU-3** Each API accepts only tokens whose `azp` is in its own `*_AUTHORIZED_PARTIES` list.
- **AU-4** An admin can't ban themselves or demote the last active admin.
- **AU-5** Role matrix:

| Capability | admin | manager | cashier |
|---|---|---|---|
| Use Admin Console API | ✅ | ✅ | ❌ |
| Use Billing Counter API | ✅ | ✅ | ✅ |
| Products / stock / orders / audit (read) | ✅ | ✅ | ❌ |
| Pricing settings (write) | ✅ | ❌ | ❌ |
| User management | ✅ | ❌ | ❌ |
| Audit / report CSV export | ✅ | ❌ | ❌ |

## 5. Clerk dashboard configuration (do once per instance: development, later production)
| Setting | Value |
|---|---|
| Application name | ShopDesk |
| Sign-in identifiers | **Username** (on) · Email (optional, so cashiers without email can still have accounts) |
| Authentication strategy | **Password** |
| Access mode | **Invite-only** (User & authentication → Access mode, `dashboard.clerk.com/~/user-authentication/access-mode`) |
| **Session token custom claims** (Sessions → Customize session token, `dashboard.clerk.com/~/sessions`) | `{ "metadata": "{{user.public_metadata}}", "username": "{{user.username}}", "name": "{{user.full_name}}" }` (Clerk's documented RBAC pattern. The role is read from `metadata.role`) |
| Session lifetime | ~8–12 h if your plan allows choosing it |
| Allowed origins / redirect URLs | dev: `http://localhost:5173`, `http://localhost:5174`. Prod: `https://admin.<domain>`, `https://pos.<domain>` |
| Webhook endpoint (prod, and dev via tunnel if wanted) | `https://admin-api.<domain>/api/webhooks/clerk`, events: `user.created`, `user.updated`, `user.deleted`, `session.created`, `session.ended`, `session.removed`, `session.revoked` |
| Bot protection | On (default) |
| MFA for admins | Turn on if your plan includes it |

Values copied into env (SETUP_GUIDE §7): `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, **JWT public key** (PEM) → `CLERK_JWT_KEY`, webhook signing secret → `CLERK_WEBHOOK_SIGNING_SECRET`.

## 6. Data model changes
Migration `0002_users`: `users` (architecture §5.1) + `webhook_events` (§5.10).

## 7. Backend design

### 7.1 Token verification (`core/clerk_auth.py`)
```python
def verify_session_token(token: str, authorized_parties: list[str]) -> ClerkClaims:
    claims = jwt.decode(
        token, settings.CLERK_JWT_KEY, algorithms=["RS256"],
        options={"require": ["exp", "iat", "sub"]}, leeway=5,
    )
    if claims.get("azp") not in authorized_parties:
        raise AuthError("TOKEN_WRONG_APP")
    role = (claims.get("metadata") or {}).get("role")
    return ClerkClaims(sub=claims["sub"], role=role, username=claims.get("username"), name=claims.get("name"))
```
- Networkless: uses the PEM public key, with no call to Clerk per request.
- Missing or invalid header → 401 `AUTH_REQUIRED` / `TOKEN_INVALID` / `TOKEN_EXPIRED`.

### 7.2 `@require_role(*roles)` (`core/security.py`)
1. Read `Authorization: Bearer …` and verify (7.1) with this app's authorized parties.
2. `auth_service.resolve_user(claims)`: look up `users.clerk_user_id`. If missing, insert it **from the verified token claims** (username, name, role), with no Clerk API call, which keeps serverless requests fast. Webhooks fill in the email later. Refresh role/name if the claims differ (audited as `user.synced`). Update `last_seen_at` (throttled to 1/min).
3. If `is_active` is false → 401 `ACCOUNT_INACTIVE`. If the role isn't allowed → 403 `ROLE_NOT_ALLOWED`, audited as `auth.role_denied` (throttled).
4. Put an `ActorContext` on `flask.g`.

A meta-test asserts that **every route** has `@require_role`, or is on the public allowlist (`/api/health`, `/api/webhooks/clerk`).

### 7.3 Webhooks (`admin_api/routes/webhooks.py`)
Verify with `svix.Webhook(CLERK_WEBHOOK_SIGNING_SECRET).verify(body, headers)`. Dedupe by `svix-id`. Handle the events listed in architecture §6.7. Return 200 quickly.

### 7.4 User management (`core/services/user_service.py`, admin only)
Uses the official `clerk-backend-api` SDK with `CLERK_SECRET_KEY`.
| Action | Clerk call | Local + audit |
|---|---|---|
| Create user | `users.create(username, password, first/last name, public_metadata={"role": r}, skip_password_checks=False)` | insert mirror, `user.create` |
| Change role | `users.update_metadata(public_metadata={"role": r})` | update mirror, `user.update` (AU-4) |
| Reset password | `users.update(password=…)` + revoke the user's sessions | `user.password_reset` |
| Deactivate | `users.ban(user_id)` | `is_active=false`, `user.deactivate` (AU-4) |
| Reactivate | `users.unban(user_id)` | `is_active=true`, `user.reactivate` |

The Clerk call happens first. If it succeeds and the DB commit fails, log an error and rely on the webhook/JIT sync to fix the mirror. (Clerk is the source of truth for identity.)

### 7.5 CLI
`flask --app admin_api promote-admin --clerk-user-id user_xxx` sets `public_metadata.role = "admin"` through the Backend API and upserts the mirror. It's used once for the owner. Alternatively, set the metadata by hand in the Clerk dashboard.

## 8. API
| Method | Path | Server | Role | Notes |
|---|---|---|---|---|
| GET | /api/auth/me | both | allowed roles for that server | `{user:{id, username, full_name, role}, server}` |
| POST | /api/webhooks/clerk | admin | svix-signed | |
| GET | /api/users | admin | admin | |
| POST | /api/users | admin | admin | `{username, full_name, role, password}` |
| PATCH | /api/users/{id} | admin | admin | `{full_name?, role?}` |
| POST | /api/users/{id}/reset-password | admin | admin | `{new_password}` |
| POST | /api/users/{id}/ban · /unban | admin | admin | |

There are no login, logout or refresh endpoints. The Clerk SDK handles them.
**Errors:** 401 `AUTH_REQUIRED`/`TOKEN_INVALID`/`TOKEN_EXPIRED`/`TOKEN_WRONG_APP`/`ACCOUNT_INACTIVE`, 403 `ROLE_NOT_ALLOWED`/`NO_ROLE_ASSIGNED`, 409 `USERNAME_TAKEN`, 422 `LAST_ADMIN`/`WEAK_PASSWORD` (from Clerk).

## 9. Frontend
- `@clerk/react` (v6+). Wrap each app in `<ClerkProvider publishableKey={import.meta.env.VITE_CLERK_PUBLISHABLE_KEY}>`.
- **Sign-in page** `/sign-in`: ShopDesk branding + Clerk `<SignIn />`, styled with `appearance` variables that match the design tokens. Sign-up links are hidden.
- Route guard: `<Show when="signed-in">` / redirect to `/sign-in`. Then call `/api/auth/me`. On 403 `ROLE_NOT_ALLOWED`, show a "Your account can't use the Admin Console" screen with a sign-out button. Note that `<Show>` only hides UI; the API enforces access.
- Axios interceptor (shared package): `config.headers.Authorization = \`Bearer ${await getToken()}\``. On 401, try `getToken({ skipCache: true })` once, then send the user to sign-in.
- Header: `<UserButton />` + a role badge from `/api/auth/me`.
- Admin **Users page**: table (username, name, role, active, last seen), Add User modal (username, full name, role, temporary password), change role, reset password, ban/unban with confirmation.

## 10. Tasks
- [x] 1. Configure the Clerk development instance per §5. Put the keys in `.env` and the frontend `.env.development.local`.
- [x] 2. `User` + `WebhookEvent` models + migration.
- [x] 3. `clerk_auth.verify_session_token` + unit tests with a locally generated RSA key pair (no network).
- [x] 4. `auth_service.resolve_user` (JIT sync) + `require_role` + `current_actor()`.
- [x] 5. `/api/auth/me` on both servers + the route-coverage meta-test.
- [x] 6. Webhook endpoint + svix verification + dedupe + tests with signed fixtures.
- [x] 7. `user_service` + Users routes (Clerk SDK mocked in tests) + AU-4.
- [x] 8. `promote-admin` CLI.
- [x] 9. Frontend: ClerkProvider, sign-in page, guard, axios interceptor, UserButton, "wrong app" screen, Users page.
- [ ] 10. Manual test: create an owner in the Clerk dashboard → promote-admin → create a cashier from the Users page → check the role matrix in both apps.

## 11. Acceptance criteria
- [x] Self sign-up is impossible: the sign-up page shows restricted, and the API rejects users without a role. *(automated test)*
- [ ] A cashier signs in to pos-web and can bill. The same cashier signed in to admin-web gets the "can't use Admin Console" screen, and the admin API returns 403.
- [x] A token minted for pos-web, sent to admin_api → 401 `TOKEN_WRONG_APP` (`azp` check). *(automated test)*
- [ ] Changing a user's role in the Users page takes effect within about a minute in both apps.
- [ ] Banning a user → their next request fails, and the UI returns to sign-in.
- [x] Webhook with a bad signature → 400. The same `svix-id` delivered twice → processed once. *(automated test)*
- [x] Sign-in, sign-out, user create/role change/ban each produce an audit row. *(automated test)*
- [x] No Clerk secret key appears in frontend code or bundles (`VITE_` vars contain only the publishable key). *(automated test)*

## 12. Tests
- Unit: JWT verification (valid, expired, wrong azp, bad signature, missing role).
- Service: JIT insert/update, inactive user, AU-4.
- API: parametrised role matrix for every route, webhook signature/dedupe, Users endpoints with the Clerk SDK mocked.
- Frontend: interceptor adds the header and retries once, guard redirects, wrong-app screen.

## 13. Implementation notes (2026-10-04)
- The `audit_logs` table + trigger + `audit_service.record/diff` were built here (migration `0002_users_audit`), so spec 05 only adds the viewer and CSV export.
- svix 2.x `Webhook.verify()` doesn't return the payload. The handler parses the JSON after verifying.
- Clerk telemetry is disabled (`telemetry={false}`).
- Tests: `tests/unit/test_clerk_auth.py`, `tests/api/test_auth.py`, `test_users.py`, `test_webhooks.py`, `test_route_security.py`, `tests/services/test_audit_service.py`.

## 14. Open questions
- Q2: manager PIN for discount? If yes, add a hashed `discount_pin` to the `users` mirror in a later spec.
