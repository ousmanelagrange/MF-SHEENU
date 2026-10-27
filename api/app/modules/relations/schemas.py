"""Schémas Pydantic du module."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import ORM, Certainty, EndReason, ParentKind, UnionKind


class ParentChildCreate(BaseModel):
    parent_id: UUID
    child_id: UUID
    kind: ParentKind = "biological"
    certainty: Certainty = "documented"
    source: str | None = None


class ParentChildUpdate(BaseModel):
    kind: ParentKind | None = None
    certainty: Certainty | None = None
    source: str | None = None


class ParentChildOut(ORM):
    id: UUID
    parent_id: UUID
    child_id: UUID
    kind: str
    certainty: str
    source: str | None


class UnionCreate(BaseModel):
    person_a_id: UUID
    person_b_id: UUID
    kind: UnionKind = "customary"
    rank: int | None = Field(default=None, ge=1, le=20)
    start_date: date | None = None
    end_date: date | None = None
    end_reason: EndReason | None = None
    certainty: Certainty = "documented"


class UnionUpdate(BaseModel):
    kind: UnionKind | None = None
    rank: int | None = Field(default=None, ge=1, le=20)
    start_date: date | None = None
    end_date: date | None = None
    end_reason: EndReason | None = None
    certainty: Certainty | None = None


class UnionOut(ORM):
    id: UUID
    person_a_id: UUID
    person_b_id: UUID
    kind: str
    rank: int | None
    start_date: date | None
    end_date: date | None
    end_reason: str | None
    certainty: str
