"""Schémas Pydantic du module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import ORM, RoleName


class InvitationCreate(BaseModel):
    person_id: UUID | None = None
    role: RoleName = "member"
    note: str | None = Field(default=None, max_length=200)
    days: int = Field(default=7, ge=1, le=60)


class InvitationOut(ORM):
    id: UUID
    person_id: UUID | None
    role: str
    note: str | None
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None


class InvitationCreated(InvitationOut):
    token: str
    link: str
    share_text: str


class InvitationPreview(BaseModel):
    family_name: str
    community: str | None
    invited_by: str
    person_name: str | None
    expires_at: datetime
    valid: bool
