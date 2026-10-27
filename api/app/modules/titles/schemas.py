"""Schémas Pydantic du module."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import ORM


class TitleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    abbreviation: str | None = Field(default=None, max_length=20)
    precedence: int = Field(default=100, ge=0, le=10000)
    badge_color: str = Field(default="#B8860B", pattern=r"^#[0-9A-Fa-f]{6}$")
    hereditary: bool = False
    description: str | None = None


class TitleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    abbreviation: str | None = None
    precedence: int | None = Field(default=None, ge=0, le=10000)
    badge_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    hereditary: bool | None = None
    description: str | None = None


class TitleOut(ORM):
    id: UUID
    name: str
    abbreviation: str | None
    precedence: int
    badge_color: str
    hereditary: bool
    description: str | None


class TitleHoldingCreate(BaseModel):
    title_id: UUID
    conferred_by: str | None = None
    conferred_on: date | None = None
    ended_on: date | None = None
    predecessor_id: UUID | None = None
    notes: str | None = None


class TitleHoldingUpdate(BaseModel):
    conferred_by: str | None = None
    conferred_on: date | None = None
    ended_on: date | None = None
    predecessor_id: UUID | None = None
    notes: str | None = None


class TitleHoldingOut(ORM):
    id: UUID
    title_id: UUID
    person_id: UUID
    conferred_by: str | None
    conferred_on: date | None
    ended_on: date | None
    predecessor_id: UUID | None
    notes: str | None
