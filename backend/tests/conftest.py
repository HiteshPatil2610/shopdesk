"""Shared pytest fixtures.

Tests always run with APP_ENV=test against TEST_DATABASE_URL (a database whose name ends in
_test — enforced by core.config). DB tests are skipped locally if that database is unreachable,
but fail in CI so a broken setup can't pass silently.
"""

import os

os.environ["APP_ENV"] = "test"
# Defaults so the suite runs in CI without a .env file; a local .env still wins for these.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost:5432/unused")

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from core.config import Settings, get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def test_db(settings: Settings) -> str:
    """Ensures the test DB is reachable, wipes it and applies all migrations once per session."""
    url = settings.effective_database_url
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        engine.dispose()
        message = f"Test database unreachable ({type(exc).__name__}). See SETUP_GUIDE.md §5."
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    from flask_migrate import upgrade

    from admin_api import create_app

    app = create_app(settings)
    with app.app_context():
        upgrade(directory="migrations")
    return url


@pytest.fixture()
def admin_app(settings: Settings):  # type: ignore[no-untyped-def]
    from admin_api import create_app

    return create_app(settings)


@pytest.fixture()
def pos_app(settings: Settings):  # type: ignore[no-untyped-def]
    from pos_api import create_app

    return create_app(settings)


@pytest.fixture()
def admin_client(admin_app):  # type: ignore[no-untyped-def]
    return admin_app.test_client()


@pytest.fixture()
def pos_client(pos_app):  # type: ignore[no-untyped-def]
    return pos_app.test_client()
