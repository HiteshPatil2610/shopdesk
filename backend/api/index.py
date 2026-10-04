"""Vercel entry point, shared by the shopdesk-admin-api and shopdesk-pos-api projects.

SHOPDESK_SERVER (set per Vercel project) picks which Flask app to build (architecture ADR A12).
Not used in local development — run `flask --app admin_api` / `flask --app pos_api` instead.
"""

import os
import sys
from pathlib import Path

# Vercel runs this file from backend/api/; make backend/ importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_server = os.environ.get("SHOPDESK_SERVER")

if _server == "admin":
    from admin_api import create_app
elif _server == "pos":
    from pos_api import create_app
else:
    raise RuntimeError("SHOPDESK_SERVER must be 'admin' or 'pos'")

app = create_app()
