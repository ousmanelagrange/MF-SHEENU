"""Schémas Pydantic du module."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.modules.persons.schemas import PersonSummary
from app.modules.relations.schemas import ParentChildOut, UnionOut


class TreeOut(BaseModel):
    root_person_id: UUID | None
    me_person_id: UUID | None
    persons: list[PersonSummary]
    parent_child: list[ParentChildOut]
    unions: list[UnionOut]


class KinshipOut(BaseModel):
    related: bool
    label: str | None
    relation_type: Literal["self", "blood", "spouse", "in_law", "none"]
    common_ancestor_id: UUID | None = None
    distance_from: int | None = None
    distance_to: int | None = None
    path: list[PersonSummary] = []


class StatsOut(BaseModel):
    persons: int
    living: int
    deceased: int
    members: int
    generations: int
    by_country: dict[str, int]
    by_generation: dict[int, int]
