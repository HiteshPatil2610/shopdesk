# Spec 05 — Audit Log

**Status:** ✅ Built for existing features; order integration follows specs 06–07 · **Depends on:** 02 (wired into 03, 04, 06, 07 as they're built) · **Server(s):** written by both, viewed on Admin

## 1. Goal
A tamper-resistant, searchable history of **every important action on both servers**: who did it, when, from which server and IP, what changed (before → after), and why. This lets the owner trace any problem back to a person and moment.

## 2. User stories
- As the **owner**, I can see that "ravi changed MP of P00042 from 300 to 320 at 10:14 from ADMIN".
- As the **owner**, I can see every sale and rejected cart with customer name, cashier and totals.
- As the **owner**, I can filter by date, user, server, action or product, and export to CSV.
- As the **owner**, I trust that nobody, including someone with the app's admin login, can edit or delete audit history through the app.

## 3. Scope
**In:** `audit_logs` table + immutability trigger, `audit_service.record()`, diff helper, the action catalogue, admin viewer API + UI + CSV export, per-entity history (product page tab).
**Out:** shipping logs to an external service (backlog), retention/archival jobs (backlog. Keep forever in v1).

## 4. Business rules touched
BR-8, BR-9. New:
- **AL-1** `audit_service.record()` runs in the **caller's transaction**. No separate commit. If the business change rolls back, so does the audit row, and the reverse is also true.
- **AL-2** The diff stores only changed fields. Money is stored as strings. Secrets (password hashes, tokens) are **never** stored. They're redacted as `"***"`.
- **AL-3** Read-only to the app. A DB trigger blocks UPDATE/DELETE. In prod, the app's DB role also has no UPDATE/DELETE grant on this table (spec 09).

## 5. Action catalogue
| Action | Entity | Source | Changes / metadata |
|---|---|---|---|
| `auth.login` / `auth.logout` | user | system (Clerk webhook `session.created` / `session.ended\|removed\|revoked`) | `{clerk_session_id}` |
| `auth.role_denied` | user | admin/pos | `{role, server}` (throttled to 1/min per user) |
| `user.create` / `user.update` / `user.deactivate` / `user.reactivate` / `user.password_reset` | user | admin | role/is_active diff |
| `user.synced` | user | system (Clerk webhook or JIT sync, when something changed outside ShopDesk, e.g. in the Clerk dashboard) | diff |

> Failed sign-in attempts and lockouts happen inside Clerk and show up in the Clerk dashboard, not in ShopDesk's audit log.
| `category.create` / `category.update` | category | admin | diff |
| `product.create` | product | admin | full initial values |
| `product.update` | product | admin | field diff |
| `product.reprice` | product | admin | MP/SP diff + `{trigger: "settings_apply" \| "recalculate" \| "cost_change"}` |
| `product.image_update` | product | admin | old/new path |
| `product.deactivate` / `product.activate` | product | admin | — |
| `pricing_settings.update` | pricing_settings | admin | diff |
| `pricing.apply` | pricing_settings | admin | `{affected_count}` |
| `stock.adjust` | product | admin | `{change, reason, note, before, after}` |
| `order.confirm` | order | pos | `{order_number, customer_name, customer_phone, cashier, discount_applied, item_count, total, lines:[{code, qty, unit_price}]}` |
| `order.reject` | order | pos | same + `reject_reason` |
| `audit.export` | audit | admin | `{filters, row_count}` |
| `report.export` | report | admin | `{report, from, to, row_count}` (spec 08) |

`summary` examples (written by the service, shown in the table):
- `P00042 Steel bottle: market_price 300.00 → 320.00`
- `INV-20261004-0007 · Amit Kumar · 3 items · ₹605.00 (discount)`
- `Login failed for 'priya' (2/5)`

## 6. Data model changes
Migration `0002_users_audit` already created the table, indexes and immutability trigger during spec 02. No new migration is needed for the viewer:
```sql
CREATE FUNCTION audit_logs_immutable() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_logs is append-only'; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_audit_logs_immutable BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable();
```
(Order matters: spec 02 may have run with a stub. This migration creates the real table. If 02 is built first, build 05's table and service right after 02.)

## 7. Service API
```python
audit_service.record(
    session, actor: ActorContext, action: str, entity_type: str, entity_id: str | int | None,
    summary: str, changes: dict | None = None, metadata: dict | None = None,
) -> None

audit_service.diff(before: dict, after: dict, redact: set[str] = {"password", "new_password"}) -> dict
# → {"market_price": ["300.00", "320.00"]}, Decimals → str, datetimes → ISO
```

## 8. HTTP API (Admin :5001)
| Method | Path | Role | Notes |
|---|---|---|---|
| GET | /api/audit-logs | mgr+ | filters: `from, to, user_id, source, action (prefix ok: "product."), entity_type, entity_id, q (summary ILIKE)`, pagination, newest first |
| GET | /api/audit-logs/{id} | mgr+ | full row |
| GET | /api/audit-logs/export.csv | admin | same filters, streamed, max 100k rows, writes `audit.export` |
| GET | /api/products/{id}/audit | mgr+ | shortcut for entity history |
| GET | /api/orders/{id}/audit | mgr+ | |

There is no POST/PUT/PATCH/DELETE for audit logs on any server. The order history shortcut will be added with the order model/routes in spec 07. Filters use ISO timestamps in the API; the UI converts IST inputs to UTC. CSV exports stream at most the newest 100,000 matching rows, include a UTF-8 BOM for Excel, and log filters/count before streaming. The export event itself is excluded from its own download.

## 9. UI
Audit log page with URL-synced filters and a read-only details modal using the existing shared Modal component. Field diffs show before/after, plus metadata/IP/user agent. Admin-only CSV button. Product edit page "Audit history" tab preserves the details form while switching views. Order detail "Audit" link follows spec 07.

## 10. Tasks
- [x] 1. Model, migration and trigger (spec 02).
- [x] 2. `audit_service.record` + `diff` + recursive secret redaction; no stub remains.
- [x] 3. Existing write services record events (auth, users, products, pricing).
- [x] 4. Viewer API + bounded streamed CSV export with formula protection.
- [x] 5. Admin table, URL filters, details modal, CSV button and product audit tab.
- [ ] 5b. Order history endpoint/link when orders are built in spec 07.
- [x] 6. API/unit/UI tests and meta-test for built catalogue/staff write flows; existing auth/image tests check their events.

## 11. Acceptance criteria
- [x] Changing a product's MP creates exactly one `product.update` row with `changes = {"market_price": ["300.00","320.00"]}`, the actor, `source='admin'` and the IP. *(test)*
- [ ] A sale on POS creates `order.confirm` with customer name, cashier and totals, `source='pos'` (spec 07).
- [x] `UPDATE audit_logs SET summary='x'` → error from the trigger (DB test).
- [x] If a product update fails BR-2, no audit row is written (same transaction). *(test)*
- [x] Password hashes never appear in any audit row (test searches all rows). *(test)*
- [x] CSV export opens correctly in Excel. A summary starting with `=` is neutralised. *(test)*
- [x] Manager can view but gets 403 on export.

## 12. Tests
- Service: diff edge cases (Decimal, None → value, nested), redaction, rollback together.
- DB: trigger blocks update/delete.
- API: filters, pagination, roles, CSV injection.

Verification (2026-10-04): 188 backend tests and 51 frontend tests pass, including existing immutable-table checks, new filters/roles/export tests, recursive redaction, CSV formula protection and IST filter conversion. Browser verified rows, details, no-result filtering and export audit event. Download-path observation timed out in the in-app browser; API tests consumed and validated the CSV bytes.
