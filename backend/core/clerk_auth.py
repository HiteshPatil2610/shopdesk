"""Verify Clerk session tokens locally (no network call per request) — spec 02 §7.1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt

from core.errors import AuthError

LEEWAY_SECONDS = 5


@dataclass(frozen=True)
class ClerkClaims:
    sub: str
    role: str | None
    username: str | None
    name: str | None
    session_id: str | None
    azp: str


def verify_session_token(
    token: str, public_key_pem: str | None, authorized_parties: list[str]
) -> ClerkClaims:
    """Check signature (RS256), expiry and that the token was issued to THIS server's frontend.

    The role comes from the custom session claim `"metadata": "{{user.public_metadata}}"`.
    """
    if not public_key_pem:
        raise AuthError("Sign-in is not configured on the server", code="AUTH_NOT_CONFIGURED")
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            public_key_pem,
            algorithms=["RS256"],
            options={"require": ["exp", "iat", "sub"]},
            leeway=LEEWAY_SECONDS,
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Session expired", code="TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid session token", code="TOKEN_INVALID") from exc

    azp = claims.get("azp")
    allowed = {p.rstrip("/") for p in authorized_parties}
    if not azp or azp.rstrip("/") not in allowed:
        raise AuthError("This sign-in belongs to a different app", code="TOKEN_WRONG_APP")

    metadata = claims.get("metadata")
    role = metadata.get("role") if isinstance(metadata, dict) else None
    return ClerkClaims(
        sub=str(claims["sub"]),
        role=role if isinstance(role, str) else None,
        username=claims.get("username") or None,
        name=claims.get("name") or None,
        session_id=claims.get("sid"),
        azp=azp,
    )
