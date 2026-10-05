"""Settings loaded from environment variables (root .env locally, project env vars on Vercel).

Every variable is documented in SETUP_GUIDE.md §7. When adding one, also add it to
.env.example and the guide.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

PLACEHOLDER_MARKERS = ("change_me", "api_key:api_secret", "ep-xxxx", "<", ">", "your_api_")


def normalize_db_url(url: str) -> str:
    """Neon and the Vercel integration hand out postgres:// or postgresql:// URLs;
    SQLAlchemy needs the psycopg 3 driver spelled out."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def db_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # General
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    tz_display: str = "Asia/Kolkata"
    currency: str = "INR"

    # Database
    database_url: str
    database_url_unpooled: str | None = None
    test_database_url: str | None = None
    db_pool_size: int = 2
    db_max_overflow: int = 3
    db_echo: bool = False

    # Servers
    admin_cors_origins: str = "http://localhost:5173"
    pos_cors_origins: str = "http://localhost:5174"

    # Clerk (required in production; specs 02+ use them)
    clerk_publishable_key: str | None = None
    clerk_secret_key: str | None = None
    clerk_jwt_key: str | None = None
    clerk_webhook_signing_secret: str | None = None
    admin_authorized_parties: str = "http://localhost:5173"
    pos_authorized_parties: str = "http://localhost:5174"

    # Cloudinary
    cloudinary_url: str | None = None
    cloudinary_folder: str = "shopdesk-dev/products"
    max_upload_mb: int = Field(default=4, ge=1, le=4)

    # Rate limiting
    ratelimit_storage_uri: str = "memory://"

    # Shop details (receipts)
    shop_name: str = "My Shop"
    shop_address: str = ""
    shop_phone: str = ""
    shop_gstin: str = ""
    receipt_footer: str = "Thank you! Visit again"

    @field_validator("database_url", "database_url_unpooled", "test_database_url")
    @classmethod
    def _normalize_urls(cls, v: str | None) -> str | None:
        return normalize_db_url(v.strip()) if v else v

    @field_validator("clerk_jwt_key")
    @classmethod
    def _unescape_pem(cls, v: str | None) -> str | None:
        # .env stores the PEM on one line with literal "\n"; Vercel may hold real newlines.
        if not v:
            return v
        pem = v.replace("\\n", "\n").strip()
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        try:
            load_pem_public_key(pem.encode())
        except ValueError as exc:
            raise ValueError(
                "CLERK_JWT_KEY is not a valid PEM public key. Run "
                "`python -m core.setup_tools fetch-clerk-key` (from backend/) to fill it in "
                "(SETUP_GUIDE §7.3)."
            ) from exc
        return pem

    @model_validator(mode="after")
    def _check_environment(self) -> Settings:
        if self.app_env == "test":
            if not self.test_database_url:
                raise ValueError("APP_ENV=test requires TEST_DATABASE_URL")
            if not db_name(self.test_database_url).endswith("_test"):
                raise ValueError(
                    "TEST_DATABASE_URL must point to a database whose name ends in '_test' "
                    "(tests wipe data)."
                )
        if self.app_env == "production":
            required = {
                "CLERK_SECRET_KEY": self.clerk_secret_key,
                "CLERK_JWT_KEY": self.clerk_jwt_key,
                "CLOUDINARY_URL": self.cloudinary_url,
            }
            missing = [k for k, v in required.items() if not v]
            if missing:
                raise ValueError(f"Missing required production settings: {', '.join(missing)}")
            if self.clerk_secret_key and self.clerk_secret_key.startswith("sk_test_"):
                raise ValueError("Production must use a Clerk live key (sk_live_...)")
            for name, value in self.model_dump().items():
                if isinstance(value, str) and any(m in value.lower() for m in PLACEHOLDER_MARKERS):
                    raise ValueError(f"{name.upper()} still contains a placeholder value")
            if not (self.clerk_secret_key or "").startswith("sk_live_"):
                raise ValueError("Production requires a Clerk live key")
            if self.clerk_publishable_key and not self.clerk_publishable_key.startswith("pk_live_"):
                raise ValueError("Production requires a Clerk live publishable key")
            if not self.ratelimit_storage_uri.startswith("rediss://"):
                raise ValueError("Production RATELIMIT_STORAGE_URI must use rediss://")
            if self.db_echo:
                raise ValueError("Production DB_ECHO must be false")
            for name in (
                "admin_cors_origins",
                "pos_cors_origins",
                "admin_authorized_parties",
                "pos_authorized_parties",
            ):
                origins = self.split_csv(getattr(self, name))
                if not origins or any(
                    urlsplit(origin).scheme != "https"
                    or not urlsplit(origin).hostname
                    or "*" in origin
                    or urlsplit(origin).path
                    or urlsplit(origin).query
                    or urlsplit(origin).fragment
                    for origin in origins
                ):
                    raise ValueError(f"Production {name.upper()} requires exact HTTPS origins")
            db_url = urlsplit(self.database_url)
            if db_url.username != "shopdesk_app":
                raise ValueError("Production DATABASE_URL must use shopdesk_app")
            if parse_qs(db_url.query).get("sslmode", [""])[0] not in {
                "require",
                "verify-ca",
                "verify-full",
            }:
                raise ValueError("Production DATABASE_URL must require TLS")
        return self

    # Derived values -------------------------------------------------------

    @property
    def effective_database_url(self) -> str:
        """URL the running app uses (pooled in dev/prod, the test DB under pytest)."""
        if self.app_env == "test" and self.test_database_url:
            return self.test_database_url  # presence enforced by _check_environment
        return self.database_url

    @property
    def migration_database_url(self) -> str:
        """Direct (unpooled) URL for Alembic."""
        if self.app_env == "test":
            return self.effective_database_url
        return self.database_url_unpooled or self.database_url

    @staticmethod
    def split_csv(value: str) -> list[str]:
        return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
