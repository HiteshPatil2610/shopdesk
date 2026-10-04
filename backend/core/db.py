"""Database setup shared by both servers.

Neon notes (architecture §9): the apps use the pooled URL (PgBouncer, transaction mode), so
psycopg's automatic prepared statements are disabled; connections are pre-pinged and recycled
because Neon scales to zero. No connection is opened at import time (fast serverless cold starts).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from core.config import Settings

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


db = SQLAlchemy(model_class=Base)


def engine_options(settings: Settings) -> dict[str, Any]:
    return {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "echo": settings.db_echo,
        "connect_args": {"prepare_threshold": None, "connect_timeout": 10},
    }


@contextmanager
def transaction() -> Iterator[None]:
    """One service call = one transaction. Commits on success, rolls back on any error."""
    try:
        yield
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
