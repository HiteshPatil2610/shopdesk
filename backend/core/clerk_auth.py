"""Verify Clerk session tokens locally (no network call per request) — spec 02 §7.1."""

from __future__ import annotations

import base64
import json
import logging
import urllib.request
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

from core.errors import AuthError

log = logging.getLogger(__name__)

LEEWAY_SECONDS = 5


def frontend_api_host(publishable_key: str) -> str:
    """pk_test_ZmFtb3Vz...JA → famous-hornet-2839.clerk.accounts.dev"""
    encoded = publishable_key.split("_", 2)[2]
    return base64.b64decode(encoded + "=" * (-len(encoded) % 4)).decode().rstrip("$")


def fetch_public_key_pem(publishable_key: str) -> str:
    """Download the instance's (public) JWT signing key from Clerk's JWKS and return it as PEM."""
    host = frontend_api_host(publishable_key)
    request = urllib.request.Request(  # noqa: S310 - fixed https URL derived from the pk
        f"https://{host}/.well-known/jwks.json", headers={"User-Agent": "shopdesk"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
        keys = json.load(response)["keys"]
    rsa_keys = [k for k in keys if k.get("kty") == "RSA"]
    if len(rsa_keys) != 1:
        raise ValueError(f"Expected one RSA key in Clerk JWKS, found {len(rsa_keys)}")

    def b64int(value: str) -> int:
        return int.from_bytes(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)), "big")

    key = RSAPublicNumbers(b64int(rsa_keys[0]["e"]), b64int(rsa_keys[0]["n"])).public_key()
    pem = key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem.decode().strip()


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
        # The reason (bad signature, not yet valid, missing claim…) goes to the server log only.
        log.warning("Rejected Clerk token: %s: %s", type(exc).__name__, exc)
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
