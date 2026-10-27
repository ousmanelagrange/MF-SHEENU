"""Schémas Pydantic du module des cotisations."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.schemas import ORM
from app.modules.persons.schemas import PersonSummary

EventKind = Literal["mourning", "wedding", "birth", "project", "annual", "other"]
PaymentMethod = Literal["mobile_money", "cash", "bank", "other"]
DueStatus = Literal["paid", "partial", "unpaid", "exempt"]


# ---------- Barèmes ----------


class ScaleIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    currency: str = Field(default="XAF", min_length=3, max_length=3)
    amounts_by_generation: dict[str, int] = Field(default_factory=dict)
    default_amount: int = Field(default=0, ge=0)
    exempt_under_age: int | None = Field(default=None, ge=0, le=30)
    include_spouses: bool = True

    @field_validator("amounts_by_generation")
    @classmethod
    def _positive(cls, v: dict[str, int]) -> dict[str, int]:
        for gen, amount in v.items():
            if not gen.lstrip("-").isdigit() or amount < 0:
                raise ValueError("Génération entière et montant positif attendus.")
        return v


class ScaleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    amounts_by_generation: dict[str, int] | None = None
    default_amount: int | None = Field(default=None, ge=0)
    exempt_under_age: int | None = Field(default=None, ge=0, le=30)
    include_spouses: bool | None = None
    active: bool | None = None


class ScaleOut(ORM):
    id: UUID
    name: str
    currency: str
    amounts_by_generation: dict[str, int]
    default_amount: int
    exempt_under_age: int | None
    include_spouses: bool
    active: bool


# ---------- Événements ----------


class EventIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    kind: EventKind = "other"
    scale_id: UUID | None = None  # sans barème : pas de montant dû calculé (collecte libre)
    description: str | None = None
    deadline: date | None = None
    target_amount: int | None = Field(default=None, ge=0)
    concerned_person_id: UUID | None = None


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    deadline: date | None = None
    target_amount: int | None = Field(default=None, ge=0)


class Totals(BaseModel):
    due: int  # total attendu (hors exemptés)
    collected: int  # paiements validés
    pending: int  # paiements déclarés, en attente de validation
    persons_due: int
    paid: int
    partial: int
    unpaid: int
    exempt: int


class EventOut(ORM):
    id: UUID
    title: str
    kind: str
    description: str | None
    currency: str
    deadline: date | None
    target_amount: int | None
    concerned_person_id: UUID | None
    status: str
    created_at: datetime
    closed_at: datetime | None
    totals: Totals | None = None
    can_manage: bool = False


class DueRow(BaseModel):
    due_id: UUID | None
    person: PersonSummary
    amount: int
    paid: int
    status: DueStatus
    exempt: bool
    note: str | None


class DueAdd(BaseModel):
    person_id: UUID
    amount: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=300)


class DueUpdate(BaseModel):
    amount: int | None = Field(default=None, ge=0)
    exempt: bool | None = None
    note: str | None = Field(default=None, max_length=300)


# ---------- Paiements ----------


class PaymentIn(BaseModel):
    person_id: UUID
    amount: int = Field(gt=0)
    method: PaymentMethod = "mobile_money"
    reference: str | None = Field(default=None, max_length=120)
    original_amount: int | None = Field(default=None, gt=0)
    original_currency: str | None = Field(default=None, min_length=3, max_length=3)


class ReviewIn(BaseModel):
    amount: int | None = Field(default=None, gt=0)  # le trésorier peut corriger le montant reçu
    note: str | None = Field(default=None, max_length=300)


class PaymentOut(ORM):
    id: UUID
    event_id: UUID
    person: PersonSummary | None = None
    amount: int
    method: str
    reference: str | None
    proof_url: str | None
    original_amount: int | None
    original_currency: str | None
    status: str
    declared_by_name: str | None = None
    review_note: str | None
    created_at: datetime
    reviewed_at: datetime | None


class PersonContribution(BaseModel):
    """Une ligne de l'historique d'une personne : un événement, son dû et ce qu'elle a payé."""

    event: EventOut
    amount: int
    paid: int
    status: DueStatus


class RecapOut(BaseModel):
    text: str
