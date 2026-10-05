"""API security headers and shared rate-limit buckets (spec 09)."""

from typing import cast

from flask import Flask, Response, current_app, request
from flask.typing import RouteCallable
from flask_limiter import Limiter

from core.clerk_auth import verify_session_token
from core.config import Settings
from core.errors import AuthError


def _identity() -> str:
    settings: Settings = current_app.config["SHOPDESK_SETTINGS"]
    server = current_app.config["SHOPDESK_SERVER"]
    parties = settings.split_csv(
        settings.admin_authorized_parties if server == "admin" else settings.pos_authorized_parties
    )
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            claims = verify_session_token(token.strip(), settings.clerk_jwt_key, parties)
            return f"user:{claims.sub}"
        except AuthError:
            pass
    # Do not trust a caller-supplied forwarding header for anonymous limits.
    return f"ip:{request.remote_addr or 'unknown'}"


def _bucket(_endpoint: str = "") -> str:
    if request.path == "/api/cart/quote":
        return "quote"
    if request.path.startswith("/api/webhooks/"):
        return "webhook"
    if request.path.endswith(".csv"):
        return "export"
    return "writes"


def _limit() -> str:
    return {"quote": "300/minute", "webhook": "60/minute", "export": "5/minute"}.get(
        _bucket(), "120/minute"
    )


def install_rate_limits(app: Flask) -> None:
    """Share write/quote/export/webhook quotas across routes, using Redis in production."""
    settings: Settings = app.config["SHOPDESK_SETTINGS"]
    if settings.app_env == "test":
        # The ordinary DB suite has isolated transactions, not production quotas.
        # Dedicated limiter tests initialize an enabled in-memory store explicitly.
        return
    limiter = Limiter(
        key_func=_identity,
        storage_uri=settings.ratelimit_storage_uri,
        key_prefix=f"shopdesk:{app.config['SHOPDESK_SERVER']}",
        headers_enabled=True,
        enabled=True,
        swallow_errors=False,
        in_memory_fallback_enabled=False,
    )
    limiter.init_app(app)
    limit = limiter.shared_limit(
        _limit,
        scope=_bucket,
        exempt_when=lambda: request.method in {"GET", "HEAD", "OPTIONS"}
        and not request.path.endswith(".csv"),
    )
    for endpoint, view in list(app.view_functions.items()):
        if endpoint != "static":
            app.view_functions[endpoint] = cast(RouteCallable, limit(view))


def install_headers(app: Flask) -> None:
    @app.after_request
    def headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        )
        response.headers["Cache-Control"] = "no-store"
        if app.config["SHOPDESK_SETTINGS"].app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
