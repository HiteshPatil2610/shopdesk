from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Role = Literal["admin", "manager", "cashier"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UserCreate(_Strict):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str = Field(min_length=2, max_length=120)
    role: Role
    password: str = Field(min_length=10, max_length=128)

    @field_validator("username")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def _not_username(cls, v: str, info: object) -> str:
        data = getattr(info, "data", {}) or {}
        if data.get("username") and v.lower() == str(data["username"]).lower():
            raise ValueError("Password must not be the same as the username")
        return v


class UserUpdate(_Strict):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: Role | None = None


class PasswordReset(_Strict):
    new_password: str = Field(min_length=10, max_length=128)
