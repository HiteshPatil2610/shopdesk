"""Shop-local time (IST by default). The DB stores UTC; days and invoice numbers follow IST."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from core.config import get_settings


def shop_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().tz_display)


def shop_today() -> date:
    return datetime.now(shop_tz()).date()


def day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """[start, end) of a shop-local calendar day, in UTC."""
    start = datetime.combine(day, time.min, tzinfo=shop_tz())
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)
