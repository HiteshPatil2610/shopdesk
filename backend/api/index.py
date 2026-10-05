"""Local compatibility entry; deployment uses root api/index.py."""

from shopdesk import create_app

app = create_app()
