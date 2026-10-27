"""Schémas Pydantic du module."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import ORM, RoleName, Sex


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
