# Spec 05 — Audit Log

**Status:** ⬜ Not started · **Depends on:** 02 (wired into 03, 04, 06, 07 as they're built) · **Server(s):** written by both, viewed on Admin

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
Migration `0005_audit_logs`: table per architecture §5.8 + indexes + trigger:
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

There is no POST/PUT/PATCH/DELETE for audit logs on any server.

## 9. UI
Audit log page and diff drawer per ui-context §3.7. Product edit page "Audit history" tab. Order detail "Audit" link.

## 10. Tasks
- [ ] 1. Model, migration and trigger.
- [ ] 2. `audit_service.record` + `diff` + redaction + summary helpers. Replace any stub from spec 02.
- [ ] 3. Make sure every existing write service calls it (auth, users, products, pricing).
- [ ] 4. Viewer API + CSV export (stream with `csv` module, escape formula injection: prefix cells starting with `= + - @` with `'`).
- [ ] 5. Admin UI: table, filters (synced to URL query), diff drawer, CSV button, product/order history tabs.
- [ ] 6. Tests, including a meta-test that runs every write endpoint and asserts that ≥ 1 audit row was created.

## 11. Acceptance criteria
- [ ] Changing a product's MP creates exactly one `product.update` row with `changes = {"market_price": ["300.00","320.00"]}`, the actor, `source='admin'` and the IP.
- [ ] A sale on POS creates `order.confirm` with customer name, cashier and totals, `source='pos'`.
- [ ] `UPDATE audit_logs SET summary='x'` in psql → error from the trigger.
- [ ] If a product update fails BR-2, no audit row is written (same transaction).
- [ ] Password hashes never appear in any audit row (test searches all rows).
- [ ] CSV export opens correctly in Excel. A summary starting with `=` is neutralised.
- [ ] Manager can view but gets 403 on export.

## 12. Tests
- Service: diff edge cases (Decimal, None → value, nested), redaction, rollback together.
- DB: trigger blocks update/delete.
- API: filters, pagination, roles, CSV injection.
