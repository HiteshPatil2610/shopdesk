"""Append-only audit trail (spec 05).

`record()` adds the row to the CURRENT session/transaction and never commits by itself (AL-1):
if the business change rolls back, its audit row rolls back too, and vice versa.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from core.actor import ActorContext
from core.db import db
from core.models import AuditLog

REDACTED = "***"
DEFAULT_REDACT = frozenset(
    {
        "password",
        "new_password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "secret",
        "api_key",
    }
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_jsonable(v) for v in value]
    return value


def _redact(data: dict[str, Any] | None, redact: frozenset[str]) -> dict[str, Any] | None:
    if data is None:
        return None
    return {
        k: (REDACTED if k.lower() in redact else _redact_value(v, redact)) for k, v in data.items()
    }


def _redact_value(value: Any, redact: frozenset[str]) -> Any:
    if isinstance(value, dict):
        return _redact(value, redact)
    if isinstance(value, list | tuple | set):
        return [_redact_value(item, redact) for item in value]
    return _jsonable(value)


def diff(
    before: dict[str, Any], after: dict[str, Any], redact: frozenset[str] = DEFAULT_REDACT
) -> dict[str, list[Any]]:
    """Only the fields that changed: {"market_price": ["300.00", "320.00"]} (AL-2)."""
    changes: dict[str, list[Any]] = {}
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old != new:
            changes[key] = (
                [REDACTED, REDACTED]
                if key.lower() in redact
                else [_redact_value(old, redact), _redact_value(new, redact)]
            )
    return changes


def record(
    actor: ActorContext,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    summary: str,
    *,
    changes: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    redact: frozenset[str] = DEFAULT_REDACT,
) -> AuditLog:
    row = AuditLog(
        actor_user_id=actor.user_id,
        actor_username=actor.username[:50],
        source=actor.source,
        action=action,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        summary=summary[:255],
        changes=_redact(changes, redact) if changes else None,
        metadata_=_redact(metadata, redact) if metadata else None,
        ip_address=actor.ip,
        user_agent=(actor.user_agent or "")[:255] or None,
    )
    db.session.add(row)
    return row
