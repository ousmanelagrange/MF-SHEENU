"""Schémas des demandes de rattachement."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.persons.schemas import PersonSummary


class JoinLinkOut(BaseModel):
    active: bool
    created_at: datetime | None
    # Fournis seulement à la création : le jeton n'est pas conservé en clair
    link: str | None = None
    share_text: str | None = None


class JoinPreview(BaseModel):
    family_name: str
    community: str | None
    already_member: bool
    request_status: str | None  # pending | accepted | rejected, si une demande existe


class JoinRequestIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    sex: Literal["M", "F", "U"] = "U"
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    lineage: str = Field(min_length=3, max_length=2000)
    village: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=32)


class JoinRequestOut(BaseModel):
    id: UUID
    first_name: str
    last_name: str | None
    sex: str
    birth_year: int | None
    lineage: str
    village: str | None
    country: str | None
    phone: str | None
    account_name: str
    status: str
    person: PersonSummary | None
    review_note: str | None
    created_at: datetime


class AcceptIn(BaseModel):
    """Où placer la personne : sur une fiche existante, comme enfant d'une personne de
    l'arbre, ou sur une nouvelle fiche à relier plus tard."""

    person_id: UUID | None = None
    parent_id: UUID | None = None
    role: Literal["member", "branch_head"] = "member"


class RejectIn(BaseModel):
    note: str = Field(min_length=2, max_length=300)
