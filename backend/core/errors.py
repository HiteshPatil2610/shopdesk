"""Application errors and the single JSON error shape:

{"error": {"code": "...", "message": "...", "details": ...}}
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, g, jsonify
from flask.typing import ResponseReturnValue
from pydantic import ValidationError as PydanticValidationError
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


class AppError(Exception):
    status = 400
    code = "APP_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status:
            self.status = status
        self.details = details


class ValidationError(AppError):
    status, code = 400, "VALIDATION_ERROR"


class AuthError(AppError):
    status, code = 401, "AUTH_REQUIRED"


class ForbiddenError(AppError):
    status, code = 403, "FORBIDDEN"


class NotFoundError(AppError):
    status, code = 404, "NOT_FOUND"


class ConflictError(AppError):
    status, code = 409, "CONFLICT"


class InsufficientStockError(ConflictError):
    code = "INSUFFICIENT_STOCK"


class BusinessRuleError(AppError):
    status, code = 422, "BUSINESS_RULE_VIOLATION"


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def _app_error(exc: AppError) -> ResponseReturnValue:
        return jsonify(error_body(exc.code, exc.message, exc.details)), exc.status

    @app.errorhandler(PydanticValidationError)
    def _validation_error(exc: PydanticValidationError) -> ResponseReturnValue:
        details = [
            {"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return jsonify(error_body("VALIDATION_ERROR", "Invalid request", details)), 400

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException) -> ResponseReturnValue:
        code = (exc.name or "HTTP_ERROR").upper().replace(" ", "_")
        return jsonify(error_body(code, exc.description or exc.name or "")), exc.code or 500

    @app.errorhandler(Exception)
    def _unexpected(exc: Exception) -> ResponseReturnValue:
        log.exception("Unhandled error")
        request_id = getattr(g, "request_id", None)
        return (
            jsonify(
                error_body(
                    "INTERNAL_ERROR",
                    "Something went wrong. Please try again.",
                    {"request_id": request_id},
                )
            ),
            500,
        )
