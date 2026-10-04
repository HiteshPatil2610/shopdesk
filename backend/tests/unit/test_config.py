import pytest
from pydantic import ValidationError

from core.config import Settings, normalize_db_url

NEON = "postgresql://u:p@ep-abc-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"


def make(**overrides) -> Settings:
    values = {
        "app_env": "development",
        "database_url": "postgresql+psycopg://u:p@localhost/shopdesk",
        "test_database_url": "postgresql+psycopg://u:p@localhost/shopdesk_test",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("prefix", ["postgres://", "postgresql://"])
def test_db_urls_are_normalised_to_psycopg(prefix):
    url = prefix + "u:p@host/db?sslmode=require"
    assert normalize_db_url(url) == "postgresql+psycopg://u:p@host/db?sslmode=require"


def test_neon_url_from_env_is_normalised():
    assert make(database_url=NEON).database_url.startswith("postgresql+psycopg://")


def test_migration_url_prefers_unpooled():
    s = make(database_url=NEON, database_url_unpooled=NEON.replace("-pooler", ""))
    assert "-pooler" not in s.migration_database_url
    assert "-pooler" in s.effective_database_url


def test_pem_escaped_newlines_are_restored(rsa_public_pem):
    one_line = rsa_public_pem.strip().replace("\n", "\\n")
    assert make(clerk_jwt_key=one_line).clerk_jwt_key == rsa_public_pem.strip()


def test_invalid_pem_fails_fast_with_fix_hint():
    shortened = "-----BEGIN PUBLIC KEY-----\\nMIIBIjANBgkqh...\\n-----END PUBLIC KEY-----"
    with pytest.raises(ValidationError, match="setup_tools fetch-clerk-key"):
        make(clerk_jwt_key=shortened)


def test_test_env_refuses_non_test_database():
    with pytest.raises(ValidationError, match="_test"):
        make(app_env="test", test_database_url="postgresql+psycopg://u:p@localhost/shopdesk")


def test_production_requires_live_clerk_key(rsa_public_pem):
    with pytest.raises(ValidationError, match="live key"):
        make(
            app_env="production",
            clerk_secret_key="sk_test_123",
            clerk_jwt_key=rsa_public_pem,
            cloudinary_url="cloudinary://k:s@cloud",
        )


def test_production_refuses_placeholders(rsa_public_pem):
    with pytest.raises(ValidationError, match="placeholder"):
        make(
            app_env="production",
            database_url="postgresql+psycopg://u:CHANGE_ME@host/db",
            clerk_secret_key="sk_live_123",
            clerk_jwt_key=rsa_public_pem,
            cloudinary_url="cloudinary://k:s@cloud",
        )


def test_production_requires_clerk_and_cloudinary():
    with pytest.raises(ValidationError, match="CLERK_SECRET_KEY"):
        make(app_env="production")


def test_missing_database_url_fails_fast(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None, app_env="development")


def test_split_csv_strips_trailing_slashes():
    assert Settings.split_csv("http://a.com/, http://b.com") == ["http://a.com", "http://b.com"]
