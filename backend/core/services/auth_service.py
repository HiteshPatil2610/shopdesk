"""Map a verified Clerk token to a local user (just-in-time mirror sync) — spec 02 §7.2."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.actor import ActorContext, Source
from core.clerk_auth import ClerkClaims
from core.clerk_gateway import ClerkUserInfo
from core.db import db, transaction
from core.errors import ForbiddenError
from core.models import ROLES, AuditLog, User
from core.models.base import utcnow
from core.services import audit_service

LAST_SEEN_THROTTLE = timedelta(minutes=1)
ROLE_DENIED_THROTTLE = timedelta(minutes=1)


def _system_actor(source: Source) -> ActorContext:
    return ActorContext(
        user_id=None, clerk_user_id=None, username="system", role="system", source=source
    )


def resolve_user(claims: ClerkClaims, source: Source) -> User:
    """Find (or create) the mirror row for this Clerk user and keep role/name in sync.

    The token claim is the source of truth for the role (it's signed by Clerk and at most
    ~60s old). A user without a valid role can't use either server (AU-2).
    """
    if claims.role not in ROLES:
        raise ForbiddenError(
            "Your account has no ShopDesk role yet. Ask the owner to assign one.",
            code="NO_ROLE_ASSIGNED",
        )

    user: User | None = db.session.scalar(select(User).where(User.clerk_user_id == claims.sub))
    if user is None:
        try:
            return _jit_insert(claims, source)
        except IntegrityError:
            # Two first requests raced; the other one created the row. Use it.
            db.session.rollback()
            user = db.session.scalar(select(User).where(User.clerk_user_id == claims.sub))
            if user is None:
                raise
    now = utcnow()
    with transaction():
        new_role: str = claims.role
        new_username = claims.username or user.username
        new_full_name = (claims.name or user.full_name)[:120]
        changes = audit_service.diff(
            {"role": user.role, "username": user.username, "full_name": user.full_name},
            {"role": new_role, "username": new_username, "full_name": new_full_name},
        )
        if changes:
            user.role, user.username, user.full_name = new_role, new_username, new_full_name
            audit_service.record(
                _system_actor(source),
                "user.synced",
                "user",
                user.id,
                f"{user.display_name} updated from Clerk",
                changes=changes,
                metadata={"via": "jit"},
            )
        if user.last_seen_at is None or now - user.last_seen_at > LAST_SEEN_THROTTLE:
            user.last_seen_at = now
    return user


def _jit_insert(claims: ClerkClaims, source: Source) -> User:
    """First sign-in: create the mirror row from the verified token claims."""
    assert claims.role is not None  # noqa: S101 - checked by resolve_user
    with transaction():
        user = User(
            clerk_user_id=claims.sub,
            username=claims.username,
            full_name=(claims.name or claims.username or "Unnamed user")[:120],
            role=claims.role,
            last_seen_at=utcnow(),
        )
        db.session.add(user)
        db.session.flush()
        audit_service.record(
            _system_actor(source),
            "user.synced",
            "user",
            user.id,
            f"First sign-in: {user.display_name} ({user.role})",
            metadata={"clerk_user_id": claims.sub, "via": "jit"},
        )
    return user


def record_role_denied(user: User, server: Source, actor: ActorContext) -> None:
    """Audit a wrong-server/role attempt, at most once a minute per user (no memory needed)."""
    cutoff = utcnow() - ROLE_DENIED_THROTTLE
    recent = db.session.scalar(
        select(AuditLog.id)
        .where(
            AuditLog.actor_user_id == user.id,
            AuditLog.action == "auth.role_denied",
            AuditLog.occurred_at > cutoff,
        )
        .limit(1)
    )
    if recent:
        return
    with transaction():
        audit_service.record(
            actor,
            "auth.role_denied",
            "user",
            user.id,
            f"{user.display_name} ({user.role}) tried to use the {server} server",
            metadata={"role": user.role, "server": server},
        )


def upsert_from_clerk(info: ClerkUserInfo, actor: ActorContext) -> User | None:
    """Apply Clerk-side changes (webhook / promote-admin) to the mirror. Caller commits."""
    user: User | None = db.session.scalar(select(User).where(User.clerk_user_id == info.id))
    if user is None:
        if info.role not in ROLES:
            return None  # gets created on first sign-in once a role is assigned
        user = User(
            clerk_user_id=info.id,
            username=info.username,
            email=info.email,
            full_name=info.full_name[:120],
            role=info.role,
            is_active=not info.banned,
        )
        db.session.add(user)
        db.session.flush()
        audit_service.record(
            actor,
            "user.synced",
            "user",
            user.id,
            f"{user.display_name} added from Clerk ({user.role})",
            metadata={"clerk_user_id": info.id},
        )
        return user

    before = {
        "role": user.role,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
    }
    after = {
        "role": info.role if info.role in ROLES else user.role,
        "username": info.username,
        "email": info.email,
        "full_name": info.full_name[:120],
        "is_active": not info.banned,
    }
    changes = audit_service.diff(before, after)
    if changes:
        for key, value in after.items():
            setattr(user, key, value)
        audit_service.record(
            actor,
            "user.synced",
            "user",
            user.id,
            f"{user.display_name} updated from Clerk",
            changes=changes,
        )
    return user
