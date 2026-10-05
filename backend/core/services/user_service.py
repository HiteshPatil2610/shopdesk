"""Staff account management through the Clerk Backend API (admin only) — spec 02 §7.4.

Clerk is the source of truth for identity: the Clerk call happens first, then the local
mirror + audit row are written in one transaction. If that commit ever fails after a
successful Clerk call, the webhook / just-in-time sync repairs the mirror.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select

from core.actor import ActorContext
from core.clerk_gateway import get_gateway
from core.db import db, transaction
from core.errors import AppError, BusinessRuleError, ConflictError, NotFoundError
from core.models import User
from core.schemas.users import PasswordReset, UserCreate, UserUpdate
from core.services import audit_service, auth_service

log = logging.getLogger(__name__)


def list_users() -> list[User]:
    return list(
        db.session.scalars(select(User).order_by(User.is_active.desc(), User.full_name)).all()
    )


def sync_users(actor: ActorContext) -> tuple[list[User], set[str]]:
    """Reconcile only after the complete Clerk directory has been fetched successfully."""
    infos = get_gateway().list_users()
    present = {info.id for info in infos}
    # Offset pagination can shift if someone removes an account while pages load.
    # Confirm absent ACTIVE accounts individually before disabling their access.
    for user in list_users():
        if user.is_active and user.clerk_user_id not in present:
            try:
                info = get_gateway().get_user(user.clerk_user_id)
            except NotFoundError:
                continue
            infos.append(info)
            present.add(info.id)
    if actor.clerk_user_id not in present:
        raise AppError(
            "Clerk's directory does not contain your signed-in account. Check that the app's Clerk keys belong to the same instance.",
            code="CLERK_DIRECTORY_MISMATCH",
            status=502,
        )
    system = ActorContext.system("clerk-directory")
    with transaction():
        for info in infos:
            auth_service.upsert_from_clerk(info, system)
        deleted = set()
        for user in list_users():
            if user.clerk_user_id not in present:
                deleted.add(user.clerk_user_id)
                if user.is_active:
                    user.is_active = False
                    audit_service.record(
                        system,
                        "user.deactivate",
                        "user",
                        user.id,
                        f"{user.display_name} was deleted in Clerk",
                        changes={"is_active": [True, False]},
                        metadata={"via": "directory"},
                    )
    return list_users(), deleted


def _get(user_id: int) -> User:
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    return user


def _active_admin_count() -> int:
    return int(
        db.session.scalar(
            select(func.count()).select_from(User).where(User.role == "admin", User.is_active)
        )
        or 0
    )


def _guard_last_admin(user: User, *, removing_admin: bool) -> None:
    """AU-4: never leave the shop without an active admin."""
    if removing_admin and user.role == "admin" and user.is_active and _active_admin_count() <= 1:
        raise BusinessRuleError(
            "This is the last active admin. Make someone else admin first.", code="LAST_ADMIN"
        )


def create_user(data: UserCreate, actor: ActorContext) -> User:
    taken = db.session.scalar(
        select(User.id).where(func.lower(User.username) == data.username, User.is_active)
    )
    if taken:
        raise ConflictError("That username is already taken", code="USERNAME_TAKEN")

    info = get_gateway().create_user(
        username=data.username,
        password=data.password,
        full_name=data.full_name,
        role=data.role,
        email=data.email,
    )
    with transaction():
        user = User(
            clerk_user_id=info.id,
            username=info.username or data.username,
            email=info.email,
            full_name=data.full_name,
            role=data.role,
        )
        db.session.add(user)
        db.session.flush()
        audit_service.record(
            actor,
            "user.create",
            "user",
            user.id,
            f"Created {user.display_name} ({user.role})",
            changes={"username": [None, user.username], "role": [None, user.role]},
        )
    return user


def update_user(user_id: int, data: UserUpdate, actor: ActorContext) -> User:
    user = _get(user_id)
    if data.role and data.role != user.role:
        if user.id == actor.user_id and user.role == "admin":
            raise BusinessRuleError("You can't change your own admin role", code="SELF_DEMOTE")
        _guard_last_admin(user, removing_admin=True)

    before = {"full_name": user.full_name, "role": user.role, "email": user.email}
    after = {
        "full_name": data.full_name or user.full_name,
        "role": data.role or user.role,
        "email": data.email or user.email,
    }
    changes = audit_service.diff(before, after)
    if not changes:
        return user

    gateway = get_gateway()
    if "role" in changes:
        gateway.set_role(user.clerk_user_id, data.role or user.role)
    if "full_name" in changes:
        gateway.set_name(user.clerk_user_id, data.full_name or user.full_name)
    if "email" in changes and after["email"]:
        gateway.set_email(user.clerk_user_id, after["email"])

    with transaction():
        user.full_name, user.role = data.full_name or user.full_name, data.role or user.role
        user.email = after["email"]
        audit_service.record(
            actor,
            "user.update",
            "user",
            user.id,
            f"Updated {user.display_name}",
            changes=changes,
        )
    return user


def reset_password(user_id: int, data: PasswordReset, actor: ActorContext) -> None:
    user = _get(user_id)
    get_gateway().reset_password(user.clerk_user_id, data.new_password)
    with transaction():
        audit_service.record(
            actor,
            "user.password_reset",
            "user",
            user.id,
            f"Password reset for {user.display_name} (signed out of all devices)",
        )


def revoke_sessions(user_id: int, actor: ActorContext) -> int:
    """Revoke the user's active Clerk sessions and audit the operation (spec 09)."""
    user = _get(user_id)
    try:
        count = get_gateway().revoke_sessions(user.clerk_user_id)
    except AppError:
        with transaction():
            audit_service.record(
                actor,
                "user.sessions_revoke_failed",
                "user",
                user.id,
                f"Session revocation failed for {user.display_name}; some sessions may have been revoked",
            )
        raise
    with transaction():
        audit_service.record(
            actor,
            "user.sessions_revoke",
            "user",
            user.id,
            f"Signed out {user.display_name} from all devices",
            metadata={"sessions_revoked": count},
        )
    return count


def set_active(user_id: int, active: bool, actor: ActorContext) -> User:
    user = _get(user_id)
    if user.is_active == active:
        return user
    if not active:
        if user.id == actor.user_id:
            raise BusinessRuleError("You can't deactivate yourself", code="SELF_DEACTIVATE")
        _guard_last_admin(user, removing_admin=True)

    gateway = get_gateway()
    if active:
        gateway.unban(user.clerk_user_id)
    else:
        gateway.ban(user.clerk_user_id)

    with transaction():
        user.is_active = active
        audit_service.record(
            actor,
            "user.reactivate" if active else "user.deactivate",
            "user",
            user.id,
            f"{'Reactivated' if active else 'Deactivated'} {user.display_name}",
            changes={"is_active": [not active, active]},
        )
    return user
