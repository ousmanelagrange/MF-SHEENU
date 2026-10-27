"""Schémas Pydantic d'entrée et de sortie de l'API."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Sex = Literal["M", "F", "U"]
Visibility = Literal["family", "branch", "board", "private"]
Certainty = Literal["documented", "oral", "uncertain"]
ParentKind = Literal["biological", "adoptive", "recognized"]
UnionKind = Literal["customary", "civil", "religious"]
EndReason = Literal["divorce", "death", "other"]
RoleName = Literal["member", "branch_head", "treasurer", "secretary", "admin"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------


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
    login: str = Field(description="E-mail ou numéro de téléphone")
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


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


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    locale: Literal["fr", "en"] | None = None


# ---------- Familles ----------


class FamilyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    community: str | None = None
    description: str | None = None
    # Fiche du créateur dans cette famille
    my_first_name: str = Field(min_length=1, max_length=120)
    my_last_name: str | None = None
    my_sex: Sex = "U"
    my_birth_date: date | None = None


class FamilyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    community: str | None = None
    description: str | None = None
    root_person_id: UUID | None = None


class FamilyOut(ORM):
    id: UUID
    name: str
    community: str | None
    description: str | None
    root_person_id: UUID | None
    created_at: datetime


class MyFamilyOut(FamilyOut):
    role: str
    person_id: UUID | None


class MemberOut(BaseModel):
    id: UUID
    user_id: UUID
    full_name: str
    email: str | None
    phone: str | None
    role: str
    status: str
    person_id: UUID | None
    branch_person_id: UUID | None
    joined_at: datetime


class MemberUpdate(BaseModel):
    role: RoleName | None = None
    status: Literal["active", "suspended"] | None = None
    person_id: UUID | None = None
    branch_person_id: UUID | None = None


# ---------- Invitations ----------


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


# ---------- Personnes ----------


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


# ---------- Liens ----------


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


# ---------- Arbre / parenté ----------


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


# ---------- Titres ----------


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


# ---------- Audit ----------


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
