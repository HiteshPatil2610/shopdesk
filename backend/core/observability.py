"""Request IDs and structured logging. Never log Authorization headers or secrets (H14)."""

from __future__ import annotations

import logging
import re
import uuid

from flask import Flask, Response, g, has_request_context, request

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class _RequestContextFilter(logging.Filter):
    def __init__(self, server: str) -> None:
        super().__init__()
        self.server = server

    def filter(self, record: logging.LogRecord) -> bool:
        record.server = self.server
        record.request_id = getattr(g, "request_id", "-") if has_request_context() else "-"
        return True


def configure_logging(server: str, level: str) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_RequestContextFilter(server))
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s server=%(server)s request_id=%(request_id)s "
            "%(name)s: %(message)s"
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # Third-party chatter (HTTP client internals) drowns out our own DEBUG logs.
    for noisy in ("httpcore", "httpx", "asyncio", "urllib3", "werkzeug"):
        logging.getLogger(noisy).setLevel(max(logging.INFO, root.level))


def register_request_id(app: Flask) -> None:
    @app.before_request
    def _assign_request_id() -> None:
        incoming = request.headers.get("X-Request-ID", "")
        g.request_id = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex

    @app.after_request
    def _echo_request_id(response: Response) -> Response:
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        return response
