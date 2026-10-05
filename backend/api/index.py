"""Compatibility entry; the backend Vercel service uses wsgi.py."""

from shopdesk import create_app

app = create_app()
