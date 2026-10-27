"""Schémas Pydantic du module."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.core.schemas import ORM


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=6, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    locale: Literal["fr", "en"] = "fr"

    @model_validator(mode="after")
    def _login_required(self) -> "RegisterIn":
        if not self.email and not self.phone:
            raise ValueError("Un e-mail ou un numéro de téléphone est requis.")
        return self


class LoginIn(BaseModel):
    login: str = Field(max_length=255, description="E-mail ou numéro de téléphone")
    password: str = Field(max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str = Field(max_length=2000)


class PasswordIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class SessionOut(BaseModel):
    id: UUID
    created_at: datetime
    last_used_at: datetime
    ip: str | None
    user_agent: str | None
    current: bool


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(ORM):
    id: UUID
    email: str | None
    phone: str | None
    full_name: str
    locale: str
    is_platform_admin: bool = False


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    locale: Literal["fr", "en"] | None = None
