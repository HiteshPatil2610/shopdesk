"""Read-only audit queries and a bounded, audited CSV export (spec 05)."""

import csv
import io
import json
from collections.abc import Iterator
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.engine import ScalarResult
from sqlalchemy.sql import Select

from core.actor import ActorContext
from core.db import db, transaction
from core.errors import NotFoundError
from core.models import AuditLog
from core.schemas.audit import AuditQuery
from core.services import audit_service

EXPORT_LIMIT = 100_000


def filtered(query: AuditQuery) -> Select[tuple[AuditLog]]:
    stmt = select(AuditLog)
    for value, column in (
        (query.user_id, AuditLog.actor_user_id),
        (query.source, AuditLog.source),
        (query.entity_type, AuditLog.entity_type),
        (query.entity_id, AuditLog.entity_id),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    if query.from_at:
        stmt = stmt.where(AuditLog.occurred_at >= query.from_at)
    if query.to_at:
        stmt = stmt.where(AuditLog.occurred_at <= query.to_at)
    if query.action:
        stmt = stmt.where(AuditLog.action.startswith(query.action, autoescape=True))
    if query.q:
        stmt = stmt.where(AuditLog.summary.icontains(query.q, autoescape=True))
    return stmt


def row_out(row: AuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "occurred_at": row.occurred_at.isoformat(),
        "actor_user_id": row.actor_user_id,
        "actor_username": row.actor_username,
        "source": row.source,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "summary": row.summary,
        "changes": row.changes,
        "metadata": row.metadata_,
        "ip_address": str(row.ip_address) if row.ip_address else None,
        "user_agent": row.user_agent,
    }


def list_rows(query: AuditQuery) -> dict[str, Any]:
    stmt = filtered(query)
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = cast(
        ScalarResult[AuditLog],
        (
            db.session.execute(
                stmt.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
                .offset((query.page - 1) * query.page_size)
                .limit(query.page_size)
            ).scalars()
        ),
    ).all()
    return {
        "items": [row_out(row) for row in rows],
        "total": total,
        "page": query.page,
        "page_size": query.page_size,
    }


def get_row(row_id: int) -> dict[str, Any]:
    row = db.session.get(AuditLog, row_id)
    if row is None:
        raise NotFoundError("Audit entry not found", code="AUDIT_NOT_FOUND")
    return row_out(row)


def csv_cell(value: Any) -> str:
    """Neutralize spreadsheet formulas, including those preceded by whitespace."""
    result = "" if value is None else str(value)
    if result.lstrip().startswith(("=", "+", "-", "@")) or result.startswith(("\t", "\r", "\n")):
        return "'" + result
    return result


def export_rows(query: AuditQuery, actor: ActorContext) -> Iterator[str]:
    """Audit the export before streaming at most 100k entries, excluding the export itself."""
    cutoff = db.session.scalar(select(func.max(AuditLog.id))) or 0
    stmt = filtered(query).where(AuditLog.id <= cutoff)
    count = min(
        db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0, EXPORT_LIMIT
    )
    with transaction():
        audit_service.record(
            actor,
            "audit.export",
            "audit",
            None,
            f"Exported {count} audit entries",
            metadata={"filters": query.model_dump(mode="json", by_alias=True), "row_count": count},
        )

    def generate() -> Iterator[str]:
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        columns = [
            "id",
            "occurred_at",
            "actor_user_id",
            "actor_username",
            "source",
            "action",
            "entity_type",
            "entity_id",
            "summary",
            "changes",
            "metadata",
            "ip_address",
            "user_agent",
        ]
        writer.writerow(columns)
        yield "\ufeff" + output.getvalue()
        rows = cast(
            ScalarResult[AuditLog],
            db.session.execute(
                stmt.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
                .limit(EXPORT_LIMIT)
                .execution_options(yield_per=500)
            ).scalars(),
        )
        for row in rows:
            data = row_out(row)
            output.seek(0)
            output.truncate(0)
            writer.writerow(
                [
                    csv_cell(
                        json.dumps(data[key], ensure_ascii=False)
                        if isinstance(data[key], dict)
                        else data[key]
                    )
                    for key in columns
                ]
            )
            yield output.getvalue()

    return generate()
