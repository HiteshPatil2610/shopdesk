"""Audit viewer is read-only; CSV downloads append an export event."""

from flask import Response, jsonify, request, stream_with_context
from flask.typing import ResponseReturnValue

from core.schemas.audit import AuditQuery
from core.security import current_actor, require_role
from core.services import audit_view_service, product_service
from shopdesk.areas import area_blueprint

bp = area_blueprint("admin", "audit", "")


@bp.get("/audit-logs")
@require_role("admin", "manager")
def list_logs() -> ResponseReturnValue:
    return jsonify(audit_view_service.list_rows(AuditQuery.model_validate(request.args.to_dict())))


@bp.get("/audit-logs/<int:row_id>")
@require_role("admin", "manager")
def get_log(row_id: int) -> ResponseReturnValue:
    return jsonify({"entry": audit_view_service.get_row(row_id)})


@bp.get("/audit-logs/export.csv")
@require_role("admin")
def export_logs() -> ResponseReturnValue:
    query = AuditQuery.model_validate(request.args.to_dict())
    stream = audit_view_service.export_rows(query, current_actor())
    return Response(
        stream_with_context(stream),
        content_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="shopdesk-audit.csv"',
            "Cache-Control": "no-store",
        },
    )


@bp.get("/products/<int:product_id>/audit")
@require_role("admin", "manager")
def product_logs(product_id: int) -> ResponseReturnValue:
    product_service.get(product_id)
    filters = {**request.args.to_dict(), "entity_type": "product", "entity_id": str(product_id)}
    return jsonify(audit_view_service.list_rows(AuditQuery.model_validate(filters)))
