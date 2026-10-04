"""Setup helpers that must work even when .env is incomplete (so they don't load Settings).

    cd backend
    .\\venv\\Scripts\\python -m core.setup_tools fetch-clerk-key

fetch-clerk-key: reads CLERK_PUBLISHABLE_KEY from the root .env, downloads that Clerk
instance's PUBLIC JWT signing key (JWKS) and writes it to CLERK_JWT_KEY in the right format.
"""

from __future__ import annotations

import sys
from pathlib import Path

from core.clerk_auth import fetch_public_key_pem, frontend_api_host

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _read_env_value(lines: list[str], key: str) -> str | None:
    for line in lines:
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"') or None
    return None


def fetch_clerk_key(env_path: Path = ENV_PATH) -> str:
    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    publishable = _read_env_value(lines, "CLERK_PUBLISHABLE_KEY")
    if not publishable or not publishable.startswith("pk_"):
        raise SystemExit("CLERK_PUBLISHABLE_KEY (pk_test_… / pk_live_…) is missing from .env")

    pem = fetch_public_key_pem(publishable)
    new_line = 'CLERK_JWT_KEY="' + pem.replace("\n", "\\n") + '"\n'
    if any(line.startswith("CLERK_JWT_KEY=") for line in lines):
        lines = [new_line if line.startswith("CLERK_JWT_KEY=") else line for line in lines]
    else:
        lines.append(new_line)
    env_path.write_text("".join(lines), encoding="utf-8")
    return frontend_api_host(publishable)


def main(argv: list[str]) -> int:
    if argv[:1] == ["fetch-clerk-key"]:
        host = fetch_clerk_key()
        print(f"CLERK_JWT_KEY updated from {host}. Restart the API servers.")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
