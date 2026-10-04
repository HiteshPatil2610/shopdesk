"""Who is doing something, and from where. Passed into every service that writes data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Source = Literal["admin", "pos", "system"]


@dataclass(frozen=True)
class ActorContext:
    user_id: int | None
    clerk_user_id: str | None
    username: str
    role: str
    source: Source
    ip: str | None = None
    user_agent: str | None = None

    @classmethod
    def system(cls, label: str = "system") -> ActorContext:
        return cls(user_id=None, clerk_user_id=None, username=label, role="system", source="system")
