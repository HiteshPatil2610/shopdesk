# Code Standards — ShopDesk

These are rules, not suggestions. Code review (human or AI) checks them.

## 1. Universal rules

1. **Money = Decimal, never float.** Python uses `decimal.Decimal`, the DB uses `NUMERIC(12,2)`, the API sends money as a JSON **string** (`"300.00"`), and the frontend displays strings and doesn't do money maths. Quantise with `ROUND_HALF_UP` to 2 places via `core.money.q2()`.
2. **The server is the authority** for prices, totals, stock and roles. The UI is only a convenience layer.
3. **Every write goes through a service** that opens a transaction and records an audit entry. No `session.commit()` in routes.
4. **No secrets in code or git.** Use env vars via `core.config`. `.env` is gitignored.
5. **Small, focused changes.** One spec task per branch/PR where possible.
6. **Tests with every change to business logic.** Pricing, stock and orders need tests before merging.
7. Keep code, the specs and `architecture.md` consistent. Update the docs in the same change.

## 2. Python (backend)

### Tooling
- Python **3.11+**. Format with **black** (line length 100). Lint with **ruff** (rules: E, F, I, B, UP, S, N, SIM). Type-check with **mypy** (`--strict` on `core/`).
- `pyproject.toml` holds all tool config. A pre-commit hook runs black, ruff and the fast tests.

### Style
- Type hints on every function signature. SQLAlchemy 2.0 `Mapped[...]` style models.
- Naming: `snake_case` functions and variables, `PascalCase` classes, `UPPER_SNAKE` constants. Modules are nouns (`product_service.py`).
- Docstrings on every public service function: what it does, which rules (BR-x) it enforces, and what it raises.
- No wildcard imports. Import order is handled by ruff `I`.
- Prefer early returns over deep nesting. Functions ≤ ~50 lines. Split if longer.

### Layering (see architecture.md §4)
```python
# routes/products.py — GOOD: thin
@bp.patch("/<int:product_id>")
@require_role("admin", "manager")
def update_product(product_id: int):
    data = ProductUpdate.model_validate(request.get_json())
    product = product_service.update(product_id, data, actor=current_actor())
    return ProductOut.model_validate(product).model_dump(mode="json"), 200
```
```python
# BAD: business logic + DB in a route
@bp.patch("/<int:id>")
def update(id):
    p = Product.query.get(id); p.market_price = float(request.json["mp"]); db.session.commit()
```

### Transactions
- One service call = one transaction: `with db.session.begin(): ...`.
- Lock rows that will be decremented: `select(Product).where(...).order_by(Product.id).with_for_update()`.
- Never catch a broad `Exception` just to hide it. Catch, log with context, and re-raise as an `AppError`.

### Errors
- `core/errors.py` defines `AppError(code, message, status, details)` and subclasses: `ValidationError(400)`, `AuthError(401)`, `ForbiddenError(403)`, `NotFoundError(404)`, `ConflictError(409)`, `InsufficientStockError(409)`.
- One Flask error handler turns them into:
```json
{ "error": { "code": "INSUFFICIENT_STOCK", "message": "Not enough stock for 1 item(s)", "details": [{"code":"P00042","requested":5,"available":3}] } }
```
- Pydantic validation errors map to `400 VALIDATION_ERROR` with field-level details.
- Never return stack traces or SQL in responses. Log them server-side.

### API conventions
- REST-ish, plural nouns: `/api/products/{id}`. Actions that aren't CRUD use verbs as sub-resources: `/deactivate`, `/confirm`.
- `GET` never changes state.
- Lists: `?page=1&page_size=25&sort=-created_at&search=...` → `{ "items": [...], "page": 1, "page_size": 25, "total": 143 }`. Max page_size 100.
- Status codes: 200 OK, 201 Created, 204 No Content, 400, 401, 403, 404, 409, 413 (upload too big), 422 (business rule broken, e.g. BR-2), 429, 500.
- Timestamps in ISO-8601 UTC (`2026-10-04T12:15:00Z`).
- Separate Pydantic schemas for **POS output** (`PosProductOut`) that do not even have cost fields (BR-12). Don't "hide" fields at runtime.

### Database and migrations
- Every schema change needs an Alembic migration, reviewed by hand. Never edit a migration that has already been applied. Add a new one instead.
- Migrations are run through `shopdesk` (`flask --app shopdesk db upgrade`).
- Constraints live in the DB too (CHECK, UNIQUE, FK, NOT NULL), not just in Python.
- Names: tables plural `snake_case`, FKs `<entity>_id`, indexes `ix_<table>_<cols>`, checks `ck_<table>_<rule>`.

### Logging
- Use the `logging` module with structured format: time, level, server, request_id, user_id, message.
- Never log passwords, `Authorization` headers, Clerk tokens, webhook secrets or full image bytes.
- Add an `X-Request-ID` to every request, and return it in the response header.

### Testing (pytest)
- `tests/unit/`: pure functions (pricing, money). Fast, no DB.
- `tests/services/`: services against a **real Postgres** test DB (local PostgreSQL `shopdesk_test`, or the `postgres` service container in CI). Never Neon `dev`/`main`. Each test runs in a rolled-back transaction.
- `tests/api/`: Flask test client per server, checking status codes, roles and response shape.
- Must-have tests: every BR-x rule, concurrent confirm (two threads, last unit), idempotent confirm, role access matrix, audit row written for every write, and that the POS API never returns cost fields.
- Coverage target: **≥ 90% on `core/services` and `core/pricing.py`**, ≥ 75% overall.
- Test names describe behaviour: `test_confirm_rejects_when_stock_insufficient`.

## 3. TypeScript / React (frontend)

### Tooling
- TypeScript **strict** mode. ESLint (typescript-eslint, react-hooks, jsx-a11y) + Prettier (2 spaces, single quotes, trailing commas, width 100).
- Vitest + React Testing Library for components and utils.

### Style
- Function components + hooks only. No class components.
- Files: components `PascalCase.tsx`, hooks `useThing.ts`, utils `camelCase.ts`. One component per file.
- Props typed with `type Props = {...}`. No `any`. Use `unknown` + narrowing if needed.
- Server state lives **only** in TanStack Query. Local UI state uses `useState`/`useReducer`. The POS cart uses a `useReducer` plus a `sessionStorage` mirror. No Redux.
- API calls only go through `features/*/api.ts` hooks, which use the shared axios instance. Components never call axios directly.
- Forms: React Hook Form + Zod schema. The Zod rules mirror the backend Pydantic rules.
- Money: keep as `string` from the API and render with `formatINR()`. **Don't add money in JS.** Totals come from the server quote.
- Don't use `dangerouslySetInnerHTML`. Escape all user content (React does this by default).
- Accessibility: labels on all inputs, buttons have text or `aria-label`, keyboard-reachable.

### Structure
See [ui-context.md §6](ui-context.md#6-frontend-folder-conventions). Shared code goes in `frontend/packages/shared`. Don't copy-paste between admin-web and pos-web.

## 4. Security rules (always on)

- Identity is handled by **Clerk**. ShopDesk never stores passwords. Passwords typed into the Users page go straight to the Clerk API and are never logged or saved.
- Verify every Clerk token's signature, expiry and **`azp`** (this server's frontend only). The role comes from the verified token claim + the local `users.is_active` mirror.
- Only the Clerk **publishable** key may appear in frontend code (`VITE_CLERK_PUBLISHABLE_KEY`). The secret key, webhook secret, Cloudinary secret and DB URLs are backend-only.
- Verify Clerk webhooks with svix before reading the body. Dedupe by `svix-id`.
- Role check on **every** endpoint (decorator). Default deny: a route with no role decorator fails a test.
- Validate every input (type, length, range). Product name ≤ 150, qty 1–10,000 per line, price 0–9,999,999.99.
- Use parameterised queries only (the SQLAlchemy ORM does this). Never format SQL strings with user input.
- File uploads: check type by **content** (Pillow open + verify), not extension. Re-encode to WebP. Strip EXIF. Max 4 MB on the server (Vercel's body limit is ~4.5 MB). The browser resizes first. Use a random UUID filename. Never use the user's filename in a path.
- Auth travels as `Authorization: Bearer` (no auth cookies), so there's no CSRF surface. Don't add cookie-based auth without updating spec 02.
- Serverless (Vercel): no in-memory state between requests, no writes to local disk, and no heavy work at import time (create DB/SDK clients lazily). Any new migration must be **backward-compatible** (expand → contract), because code and migrations deploy independently.
- Neon: the apps use the **pooled** URL, migrations use the **direct** URL. Don't rely on session state (`SET`, temp tables) across statements. Keep locks inside one transaction.
- Same-origin API: emit no CORS permission headers. Authenticate bearer tokens and enforce role ceilings per area.
- Dependencies pinned in `requirements.txt` / `package-lock.json`. Run `pip-audit` and `npm audit` before releases.

## 5. Git conventions

- Branches: `feat/03-product-crud`, `fix/pos-qty-overflow`, `docs/update-arch`, `chore/deps`.
- **Conventional Commits:** `feat(pos): apply discount toggle switches to SP`, `fix(stock): prevent negative qty on adjust`, `test(orders): concurrent confirm`.
- Commit messages say **why**, not just what. Reference the spec: `Refs: specs/07 task 3`.
- Never commit `.env`, `.env.*.local`, `node_modules/`, `__pycache__/`, `*.db` or database dumps (`*.dump`).
- `main` is always runnable. Merge only with tests and lint passing.

## 6. Definition of Done (per task)

- [ ] Code follows this document. Lint and format are clean.
- [ ] Tests added/updated and passing locally (`pytest`, `npm test`).
- [ ] Business rules touched have explicit tests.
- [ ] Writes produce audit rows (checked in a test).
- [ ] Spec acceptance criteria for the task are met.
- [ ] Docs updated (spec, architecture, progress-tracker).
- [ ] Manually tried in the browser for UI changes, including loading, error and empty states.
