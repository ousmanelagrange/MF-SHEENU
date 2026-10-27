"""Schémas Pydantic du module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.schemas import ORM


class AuditOut(ORM):
    id: UUID
    user_id: UUID | None
    user_name: str | None = None
    action: str
    entity: str
    entity_id: UUID | None
    before: dict | None
    after: dict | None
    created_at: datetime


class AuditList(BaseModel):
    items: list[AuditOut]
    total: int
