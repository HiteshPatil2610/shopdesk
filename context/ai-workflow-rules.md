# AI Workflow Rules — ShopDesk

Rules for any AI coding assistant (Claude Code, Cursor, Copilot, …) working on this repo. A human contributor should follow them too.

## 1. Before you start any task

1. Read, in order: `context/README.md` → `context/progress-tracker.md` → the relevant `context/specs/NN-*.md` → `context/architecture.md` sections it references → `context/code-standards.md`.
2. Find the **next unchecked task** in the current spec (or the task the user named).
3. If the spec is unclear, conflicts with another doc, or is missing a decision, **stop and ask**. Don't guess on business rules, money or security.
4. For anything bigger than a small fix, write a short plan first: files to touch, approach, tests. Wait for approval if the user asked to review plans.

## 2. While working

- **One spec task at a time.** Don't start the next task or "improve" unrelated code in the same change.
- Follow the layering: routes → schemas → services → models. Business logic only in `backend/core/services` or `backend/core/pricing.py`.
- Reuse what exists. Search `core/` and `frontend/packages/shared` before writing a new helper.
- Match the surrounding code style. Don't reformat files you aren't changing.
- Write or update tests **in the same change** as the code.
- Run the relevant checks before you say a task is done:
  ```bash
  cd backend && ruff check . && black --check . && pytest -q
  cd frontend && npm run lint && npm run typecheck && npm test
  ```
- If a check fails, fix it or report it clearly with the output. Never say "tests pass" if you didn't run them.

## 3. Hard rules (never break these)

| # | Never… | Instead… |
|---|---|---|
| H1 | use `float` for money anywhere (Python, SQL, TS maths) | `Decimal` / `NUMERIC(12,2)` / strings |
| H2 | trust prices, totals or roles sent by the browser | recompute on the server from the DB |
| H3 | write to the DB from a route, or skip the audit log on a write | go through a service that calls `audit_service.record()` |
| H4 | update or delete rows in `audit_logs`, or add an endpoint that does | treat it as append-only |
| H5 | change `products.quantity` without a matching `stock_movements` row | use `stock_service` |
| H6 | hard-delete products, orders, users or audit rows | soft delete (`is_active=false`) |
| H7 | expose cost price, profit or `total_cost` in any **POS** API response | use `Pos*Out` schemas without those fields |
| H8 | edit an Alembic migration that has already been applied, or hand-edit the DB schema | create a new migration |
| H9 | commit secrets (Clerk secret key, Neon URLs, Cloudinary URL, webhook secret), `.env`, or real customer data. Put a secret in a `VITE_` variable | `.env.example` with placeholders. Secrets live in `.env` (dev) and in Vercel (Production scope) / GitHub secrets (prod) |
| H10 | add a dependency without saying why | propose it with a one-line reason, then pin the version |
| H11 | change architecture, the tech stack, the DB schema or a business rule silently | propose it, get a yes, update `architecture.md` + Decision Log first |
| H12 | disable a test, lint rule or type check to make CI pass | fix the root cause, or ask |
| H13 | run destructive commands (`DROP`, `TRUNCATE`, `rm -rf`, `git push --force`, `db downgrade` on non-test DBs), reset/delete Neon branches, delete Cloudinary assets in bulk, or change Clerk production settings | ask first. Never point local commands at the Neon `main` branch without explicit permission |
| H14 | log passwords, `Authorization` headers, Clerk tokens or webhook secrets | log user id and request id only |

## 4. When a task is done

1. Re-check the task's acceptance criteria in the spec. Every box must truly be met.
2. Tick the task in the spec (`- [x]`) and in `progress-tracker.md`, and add a line to the **Session Log** there.
3. If you made a decision (library, naming, behaviour), add it to the **Decision Log**.
4. If you found a bug or tech debt outside the task, add it to **Known Issues / Backlog** instead of fixing it now.
5. Give a short summary: what changed (files), how it was tested (commands + result), and anything left open.
6. Suggest a Conventional Commit message. Commit only if the user asked.

## 5. Asking good questions

Ask when:
- a business rule is ambiguous (e.g. "should rejected orders need a reason?")
- two docs disagree
- a change would touch money, stock, auth or audit in a way the spec doesn't describe
- a requested change breaks a hard rule (explain which one and offer a safe alternative)

Ask in this format: **context → the specific question → options with a recommended one**.

## 6. Prompt templates for the human

**Start a session**
```
Read context/README.md, context/ai-workflow-rules.md and context/progress-tracker.md.
Tell me where we are, then propose the next task.
```

**Implement a spec task**
```
Implement task <N> of context/specs/<NN-name>.md.
Plan first (files + tests), wait for my OK, then build it, run the tests, and update progress-tracker.md.
```

**Review**
```
Review the current diff against context/code-standards.md and the hard rules in
context/ai-workflow-rules.md. List violations by severity. Don't fix yet.
```

**New feature**
```
Write a new spec context/specs/<NN-name>.md using spec-template.md for: <feature idea>.
Check it against project-overview business rules and flag conflicts.
```

**Debug**
```
<error / steps to reproduce>. Find the root cause before changing code.
Explain the cause, then propose the smallest fix plus a regression test.
```

## 7. Context hygiene

- Long session? Re-read `progress-tracker.md` and the current spec before continuing.
- Don't paste huge files into chat. Reference them by path.
- If the docs are out of date compared with the code, say so and fix the docs in the same change.
