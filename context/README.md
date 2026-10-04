# ShopDesk — Context Docs

This folder is the **single source of truth** for what ShopDesk is, how it's built, and how work on it (by you or an AI assistant) is done. Read these before you write code, and keep them up to date as the project changes.

## What is ShopDesk?

A product-management and billing system made of **two servers that share one PostgreSQL database**, running on managed cloud services (Vercel, Neon, Clerk, Cloudinary):

| Server | Who uses it | What it does |
|---|---|---|
| **Admin Console** (Server 1) | Owner / manager | Add and edit products (image, name, quantity, cost price), auto-calculate **Market Price (MP)** and **Selling Price (SP)** with a pricing formula, adjust stock, view sales, and read the **audit log** |
| **Billing Counter** (Server 2) | Cashier | Product list, enter **customer name**, product code and quantity, price lines at MP, **Apply Discount** (switches to SP), then **Confirm** (stock goes down) or **Reject** |

## Setting up your machine

See **[../SETUP_GUIDE.md](../SETUP_GUIDE.md)**. It covers required software, PostgreSQL setup, every `.env` variable, first run and troubleshooting.

## Reading order

| # | File | Read it when |
|---|---|---|
| 1 | [project-overview.md](project-overview.md) | First. Explains the problem, users, features, and business rules |
| 2 | [architecture.md](architecture.md) | Before writing any backend or DB code. Covers the tech stack, folder layout, DB schema and data flows |
| 3 | [ui-context.md](ui-context.md) | Before building any screen. Covers layouts, components, design tokens and keyboard shortcuts |
| 4 | [code-standards.md](code-standards.md) | Before writing or reviewing code |
| 5 | [ai-workflow-rules.md](ai-workflow-rules.md) | **Required for AI assistants.** How to pick up a task, what never to do, and when a task counts as done |
| 6 | [progress-tracker.md](progress-tracker.md) | At the start and end of every work session |
| 7 | [specs/](specs/) | When building a feature. Work through the specs in numeric order |

## Specs (build order)

| Spec | Feature | Depends on |
|---|---|---|
| [01-project-setup.md](specs/01-project-setup.md) | Monorepo, Postgres, both Flask apps, both React apps, tooling | — |
| [02-authentication.md](specs/02-authentication.md) | Clerk sign-in, roles, per-server access (`azp`), users mirror, webhooks | 01 |
| [03-product-management.md](specs/03-product-management.md) | Product CRUD, image upload, categories, product codes | 02 |
| [04-pricing-engine.md](specs/04-pricing-engine.md) | MP/SP formula, rounding, manual overrides, pricing settings | 03 |
| [05-audit-log.md](specs/05-audit-log.md) | Append-only audit trail and the audit log viewer | 02 (wire into 03, 04) |
| [06-pos-billing.md](specs/06-pos-billing.md) | Billing Counter screen: lookup, cart, discount, quote | 03, 04 |
| [07-orders-and-stock.md](specs/07-orders-and-stock.md) | Confirm/reject orders, atomic stock decrement, stock ledger, receipts | 05, 06 |
| [08-dashboard-and-reports.md](specs/08-dashboard-and-reports.md) | Sales/profit dashboard, low-stock alerts, CSV export | 07 |
| [09-security-hardening.md](specs/09-security-hardening.md) | Headers/CSP, rate limits, Neon roles, backups, review checklist | all |
| [10-deployment.md](specs/10-deployment.md) | 4 Vercel projects + Neon `main` + Clerk production + Upstash, CI/migrations/backups | all |

Use [spec-template.md](specs/spec-template.md) to write any new feature spec (`11-...md`, `12-...md`, …).

## How to use these with an AI assistant

Start each session with a prompt like:

```
Read context/README.md, context/ai-workflow-rules.md and context/progress-tracker.md.
Then implement the next unchecked task in context/specs/0X-<name>.md.
Follow context/code-standards.md. Update progress-tracker.md when done.
```

The root [CLAUDE.md](../CLAUDE.md) points Claude Code here automatically.

## Keeping docs alive

- Spec says one thing and code does another → fix whichever is wrong in the **same** change.
- New decision made → add a row to the *Decision Log* in [progress-tracker.md](progress-tracker.md).
- Architecture change → update [architecture.md](architecture.md) **before** writing the code.
