"""Shared pytest fixtures.

Tests always run with APP_ENV=test against TEST_DATABASE_URL (a database whose name ends in
_test — enforced by core.config). DB tests are skipped locally if that database is unreachable,
but fail in CI so a broken setup can't pass silently.

Each DB test runs inside an outer transaction that is rolled back afterwards (services'
commits become SAVEPOINT releases), so nothing leaks between tests — important because the
audit_logs trigger forbids deleting rows.
"""

import base64
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

os.environ["APP_ENV"] = "test"
# Defaults so the suite runs in CI without a .env file; a local .env still wins for these.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost:5432/unused")

import jwt  # noqa: E402
import pytest  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import scoped_session, sessionmaker  # noqa: E402

from core.clerk_gateway import ClerkUserInfo, set_gateway  # noqa: E402
from core.config import Settings  # noqa: E402
from core.db import db  # noqa: E402

ADMIN_ORIGIN = "http://admin.test"
POS_ORIGIN = ADMIN_ORIGIN
WEBHOOK_SECRET = "whsec_" + base64.b64encode(b"shopdesk-test-webhook-secret-32b").decode()


# --- keys & settings -----------------------------------------------------------------


@pytest.fixture(scope="session")
def rsa_private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def rsa_public_pem(rsa_private_key: rsa.RSAPrivateKey) -> str:
    return (
        rsa_private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


@pytest.fixture(scope="session")
def settings(rsa_public_pem: str) -> Settings:
    from dotenv import dotenv_values

    from core.config import REPO_ROOT

    # Read only the test database URL from local config; never use dev/main for tests.
    local = dotenv_values(REPO_ROOT / ".env")
    return Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql://unused:unused@localhost/unused",
        test_database_url=os.environ.get("TEST_DATABASE_URL") or local.get("TEST_DATABASE_URL"),
        clerk_jwt_key=rsa_public_pem,
        authorized_parties=ADMIN_ORIGIN,
        clerk_webhook_signing_secret=WEBHOOK_SECRET,
    )


@pytest.fixture()
def make_token(rsa_private_key: rsa.RSAPrivateKey):  # type: ignore[no-untyped-def]
    """Mint a Clerk-like session token signed with the test key."""

    def _make(
        sub: str = "user_admin",
        role: str | None = "admin",
        azp: str | None = ADMIN_ORIGIN,
        username: str | None = None,
        name: str | None = "Test User",
        expires_in: int = 60,
        key: Any = None,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": sub,
            "iat": now,
            "nbf": now - 1,
            "exp": now + expires_in,
            "sid": f"sess_{sub}",
            "username": username or sub.removeprefix("user_"),
            "name": name,
            "metadata": {"role": role} if role else {},
        }
        if azp:
            claims["azp"] = azp
        return jwt.encode(claims, key or rsa_private_key, algorithm="RS256")

    return _make


@pytest.fixture()
def auth_header(make_token):  # type: ignore[no-untyped-def]
    def _hdr(**kwargs: Any) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(**kwargs)}"}

    return _hdr


# --- database --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_db(settings: Settings) -> str:
    """Ensures the test DB is reachable, wipes it and applies all migrations once per session."""
    url = settings.effective_database_url
    engine = create_engine(url, connect_args={"connect_timeout": 10})
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

    from shopdesk import create_app

    app = create_app(settings)
    with app.app_context():
        upgrade(directory="migrations")
        db.engine.dispose()
    return url


# --- apps ------------------------------------------------------------------------------


@pytest.fixture()
def app(settings: Settings):
    from shopdesk import create_app

    return create_app(settings)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def dbs(test_db: str, app) -> Iterator[Any]:  # type: ignore[no-untyped-def]
    """Rolled-back DB session for the single app. Yields the session."""
    with app.app_context():
        connection = db.engine.connect()
        outer = connection.begin()
        original = db.session
        session_factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
        db.session = scoped_session(session_factory)  # type: ignore[assignment]
        try:
            yield db.session
        finally:
            db.session.remove()
            db.session = original  # type: ignore[assignment]
            outer.rollback()
            connection.close()


# --- Clerk Backend API fake ----------------------------------------------------------


@dataclass
class FakeGateway:
    users: dict[str, ClerkUserInfo] = field(default_factory=dict)
    calls: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)
    counter: int = 0

    def get_user(self, user_id: str) -> ClerkUserInfo:
        self.calls.append(("get_user", (user_id,)))
        return self.users[user_id]

    def create_user(
        self, *, username: str, password: str, full_name: str, role: str
    ) -> ClerkUserInfo:
        self.counter += 1
        self.calls.append(("create_user", (username, full_name, role)))
        info = ClerkUserInfo(
            id=f"user_new{self.counter}",
            username=username,
            email=None,
            full_name=full_name,
            role=role,
            banned=False,
        )
        self.users[info.id] = info
        return info

    def set_role(self, user_id: str, role: str) -> None:
        self.calls.append(("set_role", (user_id, role)))

    def set_name(self, user_id: str, full_name: str) -> None:
        self.calls.append(("set_name", (user_id, full_name)))

    def reset_password(self, user_id: str, password: str) -> None:
        self.calls.append(("reset_password", (user_id,)))

    def ban(self, user_id: str) -> None:
        self.calls.append(("ban", (user_id,)))

    def unban(self, user_id: str) -> None:
        self.calls.append(("unban", (user_id,)))

    def revoke_sessions(self, user_id: str) -> int:
        self.calls.append(("revoke_sessions", (user_id,)))
        return 2


@pytest.fixture()
def fake_clerk() -> Iterator[FakeGateway]:
    fake = FakeGateway()
    set_gateway(fake)
    yield fake
    set_gateway(None)


# --- staff users & headers (specs 03+) ----------------------------------------------


@pytest.fixture()
def staff(dbs):  # type: ignore[no-untyped-def]
    """One mirror user per role, already in the DB."""
    from core.models import User

    users = {
        role: User(clerk_user_id=f"user_{role}", username=role, full_name=role.title(), role=role)
        for role in ("admin", "manager", "cashier")
    }
    dbs.add_all(users.values())
    dbs.flush()
    return users


@pytest.fixture()
def as_role(staff, auth_header):  # type: ignore[no-untyped-def]
    """Staff headers always use the one app origin; pos is kept for existing test helpers."""

    def _headers(role: str, pos: bool = False) -> dict[str, str]:
        return auth_header(
            sub=f"user_{role}", role=role, username=role, azp=POS_ORIGIN if pos else ADMIN_ORIGIN
        )

    return _headers


# --- fake image store ----------------------------------------------------------------


@dataclass
class FakeMediaStore:
    uploads: list[tuple[str, int]] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    fail_upload: bool = False

    def upload(self, data: bytes, folder: str) -> str:
        if self.fail_upload:
            from core.errors import AppError

            raise AppError("upload failed", code="IMAGE_UPLOAD_FAILED", status=502)
        public_id = f"{folder}/img{len(self.uploads) + 1}"
        self.uploads.append((public_id, len(data)))
        return public_id

    def delete(self, public_id: str) -> None:
        self.deleted.append(public_id)


@pytest.fixture()
def fake_media() -> Iterator[FakeMediaStore]:
    from core.media import set_media_store

    store = FakeMediaStore()
    set_media_store(store)
    yield store
    set_media_store(None)


def png_bytes(size: tuple[int, int] = (40, 30), mode: str = "RGB") -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new(mode, size, (200, 30, 30) if mode == "RGB" else (200, 30, 30, 128)).save(buf, "PNG")
    return buf.getvalue()


def pytest_collection_modifyitems(items):  # type: ignore[no-untyped-def]
    """Tests marked `concurrency` commit for real, so they run after everything else."""
    items.sort(key=lambda item: item.get_closest_marker("concurrency") is not None)
