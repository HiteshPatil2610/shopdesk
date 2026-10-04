"""Validated filters shared by the audit viewer and CSV export."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AuditQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    from_at: datetime | None = Field(default=None, alias="from")
    to_at: datetime | None = Field(default=None, alias="to")
    user_id: int | None = Field(default=None, ge=1)
    source: Literal["admin", "pos", "system"] | None = None
    action: str | None = Field(default=None, max_length=50)
    entity_type: str | None = Field(default=None, max_length=30)
    entity_id: str | None = Field(default=None, max_length=40)
    q: str | None = Field(default=None, max_length=100)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)

    @field_validator("from_at", "to_at")
    @classmethod
    def aware_date(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value

    @model_validator(mode="after")
    def ordered_dates(self) -> "AuditQuery":
        if self.from_at and self.to_at and self.from_at > self.to_at:
            raise ValueError("From date must be before the to date")
        return self
