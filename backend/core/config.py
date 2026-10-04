"""Settings loaded from environment variables (root .env locally, project env vars on Vercel).

Every variable is documented in SETUP_GUIDE.md §7. When adding one, also add it to
.env.example and the guide.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

PLACEHOLDER_MARKERS = ("CHANGE_ME", "API_KEY:API_SECRET", "ep-xxxx")


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
        return v.replace("\\n", "\n").strip() if v else v

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
                if isinstance(value, str) and any(m in value for m in PLACEHOLDER_MARKERS):
                    raise ValueError(f"{name.upper()} still contains a placeholder value")
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
