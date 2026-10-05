"""Thin wrapper over the Clerk Backend SDK (clerk-backend-api).

Keeps SDK details in one place, turns Clerk errors into AppErrors with readable messages,
and is easy to replace with a fake in tests (`set_gateway`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from core.config import get_settings
from core.errors import AppError, BusinessRuleError, ConflictError, NotFoundError


@dataclass(frozen=True)
class ClerkUserInfo:
    id: str
    username: str | None
    email: str | None
    full_name: str
    role: str | None
    banned: bool


class ClerkGateway(Protocol):
    def get_user(self, user_id: str) -> ClerkUserInfo: ...
    def list_users(self) -> list[ClerkUserInfo]: ...
    def create_user(
        self, *, username: str, password: str, full_name: str, role: str, email: str | None = None
    ) -> ClerkUserInfo: ...
    def set_role(self, user_id: str, role: str) -> None: ...
    def set_name(self, user_id: str, full_name: str) -> None: ...
    def set_email(self, user_id: str, email: str) -> None: ...
    def reset_password(self, user_id: str, password: str) -> None: ...
    def ban(self, user_id: str) -> None: ...
    def unban(self, user_id: str) -> None: ...
    def revoke_sessions(self, user_id: str) -> int: ...


def split_name(full_name: str) -> tuple[str, str | None]:
    parts = full_name.strip().split(maxsplit=1)
    return parts[0], (parts[1] if len(parts) > 1 else None)


def user_info_from_payload(data: dict[str, Any]) -> ClerkUserInfo:
    """Build ClerkUserInfo from a Clerk user JSON object (webhook payload / SDK model dump)."""
    email = None
    primary_id = data.get("primary_email_address_id")
    for item in data.get("email_addresses") or []:
        if item.get("id") == primary_id or email is None:
            email = item.get("email_address")
    full_name = " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p).strip()
    username = data.get("username")
    metadata = data.get("public_metadata") or {}
    role = metadata.get("role") if isinstance(metadata, dict) else None
    return ClerkUserInfo(
        id=data["id"],
        username=username,
        email=email,
        full_name=full_name or username or "Unnamed user",
        role=role if isinstance(role, str) else None,
        banned=bool(data.get("banned")),
    )


class SdkClerkGateway:
    def __init__(self, secret_key: str) -> None:
        from clerk_backend_api import Clerk

        self._clerk = Clerk(bearer_auth=secret_key)

    def _call(self, fn: Any, **kwargs: Any) -> Any:
        from clerk_backend_api import models

        try:
            return fn(**kwargs)
        except models.ClerkErrors as exc:
            if exc.status_code == 404:
                raise NotFoundError(
                    "This Clerk account no longer exists. Refresh the user list.",
                    code="CLERK_USER_NOT_FOUND",
                ) from exc
            errors = getattr(exc.data, "errors", None) or []
            first = errors[0] if errors else None
            code = getattr(first, "code", "") or ""
            message = (
                getattr(first, "long_message", None)
                or getattr(first, "message", None)
                or "Clerk rejected the request"
            )
            if "exists" in code or "taken" in code:
                raise ConflictError(message, code="IDENTIFIER_TAKEN") from exc
            if "password" in code:
                raise BusinessRuleError(message, code="WEAK_PASSWORD") from exc
            raise BusinessRuleError(message, code="CLERK_REJECTED") from exc
        except models.SDKError as exc:
            if exc.status_code == 404:
                raise NotFoundError(
                    "This Clerk account no longer exists. Refresh the user list.",
                    code="CLERK_USER_NOT_FOUND",
                ) from exc
            raise AppError(
                "Could not reach the sign-in service. Try again.",
                code="CLERK_UNAVAILABLE",
                status=502,
            ) from exc

    def _info(self, user: Any) -> ClerkUserInfo:
        return user_info_from_payload(user.model_dump(mode="json"))

    def get_user(self, user_id: str) -> ClerkUserInfo:
        return self._info(self._call(self._clerk.users.get, user_id=user_id))

    def list_users(self) -> list[ClerkUserInfo]:
        users: list[ClerkUserInfo] = []
        offset = 0
        while True:
            rows = self._call(
                self._clerk.users.list,
                request={"limit": 100, "offset": offset, "order_by": "+created_at"},
                timeout_ms=3000,
            )
            users.extend(self._info(row) for row in rows)
            if len(rows) < 100:
                return users
            offset += len(rows)

    def create_user(
        self, *, username: str, password: str, full_name: str, role: str, email: str | None = None
    ) -> ClerkUserInfo:
        first, last = split_name(full_name)
        user = self._call(
            self._clerk.users.create,
            username=username,
            password=password,
            first_name=first,
            last_name=last,
            public_metadata={"role": role},
            **({"email_address": [email]} if email else {}),
        )
        return self._info(user)

    def set_role(self, user_id: str, role: str) -> None:
        self._call(
            self._clerk.users.update_metadata, user_id=user_id, public_metadata={"role": role}
        )

    def set_name(self, user_id: str, full_name: str) -> None:
        first, last = split_name(full_name)
        self._call(self._clerk.users.update, user_id=user_id, first_name=first, last_name=last)

    def set_email(self, user_id: str, email: str) -> None:
        """Admin-attested primary email; retain other addresses and do not send notifications."""
        user = self._call(self._clerk.users.get, user_id=user_id)
        for address in user.email_addresses:
            if address.email_address.lower() == email.lower():
                self._call(
                    self._clerk.email_addresses.update,
                    email_address_id=address.id,
                    verified=True,
                    primary=True,
                    notify_primary_email_address_changed=False,
                )
                return
        self._call(
            self._clerk.email_addresses.create,
            request={
                "user_id": user_id,
                "email_address": email,
                "verified": True,
                "primary": True,
                "notify_primary_email_address_changed": False,
            },
        )

    def reset_password(self, user_id: str, password: str) -> None:
        self._call(
            self._clerk.users.update,
            user_id=user_id,
            password=password,
            sign_out_of_other_sessions=True,
        )

    def ban(self, user_id: str) -> None:
        self._call(self._clerk.users.ban, user_id=user_id)

    def unban(self, user_id: str) -> None:
        self._call(self._clerk.users.unban, user_id=user_id)

    def revoke_sessions(self, user_id: str) -> int:
        # Collect before revoking: changing active sessions while paginating would skip rows.
        ids: list[str] = []
        offset = 0
        while True:
            rows = self._call(
                self._clerk.sessions.list,
                user_id=user_id,
                status="active",
                paginated=True,
                limit=100,
                offset=offset,
            )
            ids.extend(row.id for row in rows)
            if len(rows) < 100:
                break
            offset += len(rows)
        for session_id in ids:
            self._call(self._clerk.sessions.revoke, session_id=session_id)
        return len(ids)


_gateway: ClerkGateway | None = None


def get_gateway() -> ClerkGateway:
    global _gateway
    if _gateway is None:
        secret = get_settings().clerk_secret_key
        if not secret:
            raise AppError("CLERK_SECRET_KEY is not set", code="AUTH_NOT_CONFIGURED", status=503)
        _gateway = SdkClerkGateway(secret)
    return _gateway


def set_gateway(gateway: ClerkGateway | None) -> None:
    """Tests inject a fake; None resets to the real SDK."""
    global _gateway
    _gateway = gateway
