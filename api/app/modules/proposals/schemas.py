"""Schémas Pydantic du module des propositions."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import ORM
from app.modules.persons.schemas import PersonUpdate

ProposalKind = Literal[
    "create_person",
    "update_person",
    "archive_person",
    "add_parent_child",
    "add_union",
    "delete_parent_child",
    "delete_union",
]


class ProposalCreate(BaseModel):
    """Une proposition = le type d'opération + les mêmes données que la route directe.

    Exemples de `payload` :
    - create_person : le corps de POST /persons
    - update_person : {"person_id": ..., "changes": {...corps de PATCH /persons/{id}}}
    - archive_person : {"person_id": ...}
    - add_parent_child : le corps de POST /relations/parent-child
    - add_union : le corps de POST /unions
    - delete_parent_child : {"link_id": ...}
    - delete_union : {"union_id": ...}
    """

    kind: ProposalKind
    payload: dict
    message: str | None = Field(default=None, max_length=1000)


# Corps spécifiques des opérations qui ne réutilisent pas un schéma existant
class UpdatePersonPayload(BaseModel):
    person_id: UUID
    changes: PersonUpdate


class PersonRef(BaseModel):
    person_id: UUID


class LinkRef(BaseModel):
    link_id: UUID


class UnionRef(BaseModel):
    union_id: UUID


class ReviewIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ProposalOut(ORM):
    id: UUID
    kind: str
    payload: dict
    summary: str
    message: str | None
    status: str
    author_id: UUID
    author_name: str | None = None
    reviewer_id: UUID | None
    reviewer_name: str | None = None
    review_note: str | None
    result_id: UUID | None
    created_at: datetime
    reviewed_at: datetime | None
    can_review: bool = False


class ProposalCounts(BaseModel):
    to_review: int
    mine_pending: int
