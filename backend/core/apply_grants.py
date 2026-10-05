"""Apply the reviewed grants script using the migration owner URL; manual/CI only."""

import sys
from pathlib import Path

import psycopg

from core.config import get_settings


def main() -> None:
    script = Path(sys.argv[1]).read_text(encoding="utf-8-sig")
    url = get_settings().migration_database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(script, prepare=False)
    print("Runtime and backup grants applied.")


if __name__ == "__main__":
    main()
