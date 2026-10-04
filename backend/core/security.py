"""Route protection: @require_role and @public (spec 02 §7.2).

Every route must carry one of the two — a meta-test fails otherwise (default deny).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from flask import current_app, g, request

from core.actor import ActorContext, Source
from core.clerk_auth import verify_session_token
from core.config import Settings
from core.errors import AuthError, ForbiddenError
from core.services import auth_service

F = TypeVar("F", bound=Callable[..., Any])

# Which roles may use which server at all (AU-5).
SERVER_ROLES: dict[str, frozenset[str]] = {
    "admin": frozenset({"admin", "manager"}),
    "pos": frozenset({"admin", "manager", "cashier"}),
}
ALL_ROLES = ("admin", "manager", "cashier")


def public[V: Callable[..., Any]](view: V) -> V:
    """Mark a route as intentionally unauthenticated (health check, signed webhooks)."""
    view._shopdesk_public = True  # type: ignore[attr-defined]
    return view


def _bearer_token() -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthError("Please sign in", code="AUTH_REQUIRED")
    return token.strip()


def _client_ip() -> str | None:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() or request.remote_addr


def authenticate() -> ActorContext:
    settings: Settings = current_app.config["SHOPDESK_SETTINGS"]
    server: Source = current_app.config["SHOPDESK_SERVER"]
    parties = settings.split_csv(
        settings.admin_authorized_parties if server == "admin" else settings.pos_authorized_parties
    )
    claims = verify_session_token(_bearer_token(), settings.clerk_jwt_key, parties)
    user = auth_service.resolve_user(claims, server)
    if not user.is_active:
        raise AuthError("This account has been deactivated", code="ACCOUNT_INACTIVE")
    return ActorContext(
        user_id=user.id,
        clerk_user_id=user.clerk_user_id,
        username=user.display_name,
        role=user.role,
        source=server,
        ip=_client_ip(),
        user_agent=request.headers.get("User-Agent"),
    )


def require_role(*roles: str) -> Callable[[F], F]:
    """Allow only these roles — and never a role the current server doesn't permit."""
    unknown = set(roles) - set(ALL_ROLES)
    if unknown or not roles:
        raise ValueError(f"Bad roles for require_role: {roles}")

    def decorator(view: F) -> F:
        @wraps(view)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            actor = authenticate()
            server = current_app.config["SHOPDESK_SERVER"]
            allowed = set(roles) & SERVER_ROLES[server]
            if actor.role not in allowed:
                from core.db import db
                from core.models import User

                user = db.session.get(User, actor.user_id)
                if user is not None:
                    auth_service.record_role_denied(user, server, actor)
                if actor.role not in SERVER_ROLES[server]:
                    message = (
                        "Your account can't use the Admin Console"
                        if server == "admin"
                        else "Your account can't use the Billing Counter"
                    )
                else:
                    message = "You don't have permission to do this"
                raise ForbiddenError(message, code="ROLE_NOT_ALLOWED")
            g.actor = actor
            return view(*args, **kwargs)

        wrapper._shopdesk_roles = roles  # type: ignore[attr-defined]
        return cast(F, wrapper)

    return decorator


def current_actor() -> ActorContext:
    actor = getattr(g, "actor", None)
    if actor is None:
        raise AuthError("Please sign in", code="AUTH_REQUIRED")
    return cast(ActorContext, actor)
