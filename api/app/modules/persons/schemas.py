"""Schémas Pydantic du module."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import Sex, UnionKind, Visibility


class PersonBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    traditional_name: str | None = None
    nickname: str | None = None
    sex: Sex = "U"
    birth_date: date | None = None
    birth_year: int | None = Field(default=None, ge=1000, le=2200)
    birth_place: str | None = None
    death_date: date | None = None
    death_year: int | None = Field(default=None, ge=1000, le=2200)
    death_place: str | None = None
    is_living: bool = True
    village: str | None = None
    country: str | None = None
    biography: str | None = None
    phone: str | None = None
    email: str | None = None
    contact_visibility: Visibility = "family"


class PersonCreate(PersonBase):
    parent_ids: list[UUID] = Field(default_factory=list, max_length=2)
    spouse_id: UUID | None = None
    union_kind: UnionKind = "customary"
    union_rank: int | None = Field(default=None, ge=1, le=20)


class PersonUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = None
    traditional_name: str | None = None
    nickname: str | None = None
    sex: Sex | None = None
    birth_date: date | None = None
    birth_year: int | None = Field(default=None, ge=1000, le=2200)
    birth_place: str | None = None
    death_date: date | None = None
    death_year: int | None = Field(default=None, ge=1000, le=2200)
    death_place: str | None = None
    is_living: bool | None = None
    village: str | None = None
    country: str | None = None
    biography: str | None = None
    phone: str | None = None
    email: str | None = None
    contact_visibility: Visibility | None = None


class TitleBadge(BaseModel):
    holding_id: UUID
    title_id: UUID
    name: str
    abbreviation: str | None
    precedence: int
    badge_color: str
    active: bool


class PersonSummary(BaseModel):
    id: UUID
    first_name: str
    last_name: str | None
    traditional_name: str | None
    display_name: str
    sex: str
    birth_year: int | None
    death_year: int | None
    is_living: bool
    photo_url: str | None
    generation: int | None
    titles: list[TitleBadge] = []
    has_account: bool = False


class PersonOut(PersonSummary):
    nickname: str | None
    birth_date: date | None
    birth_place: str | None
    death_date: date | None
    death_place: str | None
    village: str | None
    country: str | None
    biography: str | None
    phone: str | None
    email: str | None
    contact_visibility: str
    created_at: datetime
    updated_at: datetime
    can_edit: bool = False


class RelativeLink(BaseModel):
    relation_id: UUID
    kind: str
    certainty: str
    person: PersonSummary


class SpouseLink(BaseModel):
    union_id: UUID
    kind: str
    rank: int | None
    start_date: date | None
    end_date: date | None
    end_reason: str | None
    person: PersonSummary


class PersonDetail(PersonOut):
    parents: list[RelativeLink] = []
    children: list[RelativeLink] = []
    spouses: list[SpouseLink] = []
    siblings: list[PersonSummary] = []


class PersonList(BaseModel):
    items: list[PersonSummary]
    total: int


class RelativeDepth(BaseModel):
    person: PersonSummary
    depth: int
