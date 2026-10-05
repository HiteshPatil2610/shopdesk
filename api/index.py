"""Legacy WSGI entry; Vercel services deploy backend/wsgi.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from shopdesk import create_app  # noqa: E402

app = create_app()
