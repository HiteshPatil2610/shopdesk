"""Dashboard & reports (spec 08). Managers and admins; the sales CSV is admin-only."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from flask import Blueprint, Response, jsonify, request, stream_with_context
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.security import current_actor, require_role
from core.services import report_service
from core.timeutil import shop_today

bp = Blueprint("reports", __name__, url_prefix="/api/reports")

STAFF = ("admin", "manager")
MAX_DAYS = 366


class RangeQuery(BaseModel):
    """from/to are shop-local dates, inclusive. Defaults to the last 14 days."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    from_date: date | None = Field(default=None, alias="from")
    to_date: date | None = Field(default=None, alias="to")
    limit: int = Field(default=5, ge=1, le=50)
    by: Literal["qty", "revenue"] = "revenue"

    @model_validator(mode="after")
    def _defaults_and_bounds(self) -> RangeQuery:
        self.to_date = self.to_date or shop_today()
        self.from_date = self.from_date or self.to_date - timedelta(days=13)
        if self.from_date > self.to_date:
            raise ValueError("The start date must be on or before the end date")
        if (self.to_date - self.from_date).days + 1 > MAX_DAYS:
            raise ValueError(f"Choose at most {MAX_DAYS} days")
        return self

    @property
    def bounds(self) -> tuple[date, date]:
        assert self.from_date and self.to_date  # noqa: S101 - set by the validator
        return self.from_date, self.to_date


class DayQuery(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    day: date | None = Field(default=None, alias="date")


@bp.get("/summary")
@require_role(*STAFF)
def summary() -> ResponseReturnValue:
    day = DayQuery.model_validate(request.args.to_dict()).day or shop_today()
    return jsonify(report_service.summary(day))


@bp.get("/sales-by-day")
@require_role(*STAFF)
def sales_by_day() -> ResponseReturnValue:
    q = RangeQuery.model_validate(request.args.to_dict())
    return jsonify({"items": report_service.sales_by_day(*q.bounds)})


@bp.get("/top-products")
@require_role(*STAFF)
def top_products() -> ResponseReturnValue:
    q = RangeQuery.model_validate(request.args.to_dict())
    return jsonify({"items": report_service.top_products(*q.bounds, q.limit, q.by)})


@bp.get("/low-stock")
@require_role(*STAFF)
def low_stock() -> ResponseReturnValue:
    return jsonify({"items": report_service.low_stock()})


@bp.get("/cashiers")
@require_role(*STAFF)
def cashiers() -> ResponseReturnValue:
    q = RangeQuery.model_validate(request.args.to_dict())
    return jsonify({"items": report_service.cashiers(*q.bounds)})


@bp.get("/sales.csv")
@require_role("admin")
def sales_csv() -> ResponseReturnValue:
    q = RangeQuery.model_validate(request.args.to_dict())
    start, end = q.bounds
    stream = report_service.sales_csv(start, end, current_actor())
    return Response(
        stream_with_context(stream),
        content_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="shopdesk-sales-{start}-to-{end}.csv"',
            "Cache-Control": "no-store",
        },
    )
