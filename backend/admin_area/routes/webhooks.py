"""POST /api/webhooks/clerk — keeps the users mirror in sync and audits sign-ins (spec 02 §7.3).

Public, but every request must carry a valid svix signature. Deliveries are deduped by svix-id.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from svix.webhooks import Webhook, WebhookVerificationError

from core.actor import ActorContext
from core.clerk_gateway import user_info_from_payload
from core.config import Settings
from core.db import db, transaction
from core.errors import AppError
from core.models import User, WebhookEvent
from core.security import public
from core.services import audit_service, auth_service

log = logging.getLogger(__name__)
bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")

SESSION_END_EVENTS = {"session.ended", "session.removed", "session.revoked"}


@bp.post("/clerk")
@public
def clerk_webhook() -> ResponseReturnValue:
    settings: Settings = current_app.config["SHOPDESK_SETTINGS"]
    if not settings.clerk_webhook_signing_secret:
        raise AppError("Webhooks are not configured", code="WEBHOOK_NOT_CONFIGURED", status=503)

    payload = request.get_data()
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        # svix 2.x only verifies (returns nothing useful); parse the body after it passes.
        Webhook(settings.clerk_webhook_signing_secret).verify(payload, headers)
        event: dict[str, Any] = json.loads(payload)
    except WebhookVerificationError as exc:
        raise AppError("Invalid webhook signature", code="BAD_SIGNATURE", status=400) from exc
    except ValueError as exc:
        raise AppError("Webhook body is not JSON", code="BAD_PAYLOAD", status=400) from exc

    svix_id = headers.get("svix-id", "")
    event_type = str(event.get("type", ""))
    data = event.get("data") or {}
    system = ActorContext.system("clerk-webhook")

    try:
        with transaction():
            db.session.add(WebhookEvent(svix_id=svix_id[:64], type=event_type[:64]))
            db.session.flush()
            _handle(event_type, data, system)
    except IntegrityError:
        db.session.rollback()
        return jsonify({"status": "duplicate"}), 200
    return jsonify({"status": "ok"}), 200


def _handle(event_type: str, data: dict[str, Any], system: ActorContext) -> None:
    if event_type in {"user.created", "user.updated"}:
        auth_service.upsert_from_clerk(user_info_from_payload(data), system)
    elif event_type == "user.deleted":
        user = _mirror(data.get("id"))
        if user and user.is_active:
            user.is_active = False
            audit_service.record(
                system,
                "user.deactivate",
                "user",
                user.id,
                f"{user.display_name} was deleted in Clerk",
                changes={"is_active": [True, False]},
            )
    elif event_type == "session.created" or event_type in SESSION_END_EVENTS:
        user = _mirror(data.get("user_id"))
        if user is None:
            return
        actor = ActorContext(
            user_id=user.id,
            clerk_user_id=user.clerk_user_id,
            username=user.display_name,
            role=user.role,
            source="system",
        )
        signed_in = event_type == "session.created"
        audit_service.record(
            actor,
            "auth.login" if signed_in else "auth.logout",
            "user",
            user.id,
            f"{user.display_name} signed {'in' if signed_in else 'out'}",
            metadata={"clerk_session_id": data.get("id"), "event": event_type},
        )
    else:
        log.info("Ignoring Clerk webhook event %s", event_type)


def _mirror(clerk_user_id: Any) -> User | None:
    if not clerk_user_id:
        return None
    return db.session.scalar(select(User).where(User.clerk_user_id == str(clerk_user_id)))
