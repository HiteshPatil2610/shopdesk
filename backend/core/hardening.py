"""API security headers and shared rate-limit buckets (spec 09)."""

import io
from typing import cast

from flask import Flask, Response, current_app, request
from flask.typing import RouteCallable
from flask_limiter import Limiter
from werkzeug.exceptions import RequestEntityTooLarge

from core.clerk_auth import verify_session_token
from core.config import Settings
from core.errors import AuthError


def _identity() -> str:
    settings: Settings = current_app.config["SHOPDESK_SETTINGS"]
    parties = settings.split_csv(settings.authorized_parties)
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
    if request.path == "/api/auth/me":
        return "auth"
    if request.path == "/api/pos/cart/quote":
        return "pos:quote"
    if request.path.startswith("/api/webhooks/"):
        return "webhook"
    area = "admin" if request.path.startswith("/api/admin/") else "pos"
    return f"{area}:export" if request.path.endswith(".csv") else f"{area}:writes"


def _limit() -> str:
    return {
        "pos:quote": "300/minute",
        "webhook": "60/minute",
        "admin:export": "5/minute",
        "auth": "60/minute",
    }.get(_bucket(), "120/minute")


def _exempt() -> bool:
    if request.path == "/api/auth/me":
        return _identity().startswith("user:")
    return request.method in {"GET", "HEAD", "OPTIONS"} and not request.path.endswith(".csv")


def install_body_limits(app: Flask) -> None:
    """Bound even streamed requests before auth; only explicit image uploads get 4 MB."""

    @app.before_request
    def body_limit() -> None:
        image_route = (
            request.method == "POST"
            and request.endpoint in {"products.create_product", "products.replace_image"}
            and request.mimetype == "multipart/form-data"
        )
        small = 256 * 1024
        request.max_content_length = app.config["MAX_CONTENT_LENGTH"] if image_route else small
        if request.content_length is None and request.environ.get("wsgi.input_terminated"):
            maximum = request.max_content_length or small
            raw = request.environ["wsgi.input"].read(maximum + 1)
            if len(raw) > maximum:
                raise RequestEntityTooLarge()
            request.environ["wsgi.input"] = io.BytesIO(raw)
            request.environ["CONTENT_LENGTH"] = str(len(raw))
        # Cache for downstream JSON and multipart parsers; WSGI terminated streams are bounded.
        data = request.get_data(cache=True)
        if image_route and len(data) > small and "image" not in request.files:
            raise RequestEntityTooLarge()


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
        key_prefix="shopdesk",
        headers_enabled=True,
        enabled=True,
        swallow_errors=False,
        in_memory_fallback_enabled=False,
    )
    limiter.init_app(app)
    limit = limiter.shared_limit(
        _limit,
        scope=_bucket,
        exempt_when=_exempt,
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
