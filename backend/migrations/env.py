"""Alembic environment for ShopDesk.

Migrations always use the DIRECT (unpooled) Neon URL — PgBouncer transaction pooling doesn't
suit DDL/migration sessions (architecture §9). Under APP_ENV=test the test database is used.
"""

import logging
from logging.config import fileConfig

from alembic import context
from flask import current_app
from sqlalchemy import create_engine, pool

from core.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

target_metadata = current_app.extensions["migrate"].db.metadata


def _url() -> str:
    return get_settings().migration_database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    def process_revision_directives(context, revision, directives):  # type: ignore[no-untyped-def]
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("No changes in schema detected.")

    engine = create_engine(_url(), poolclass=pool.NullPool, connect_args={"connect_timeout": 15})
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            process_revision_directives=process_revision_directives,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
