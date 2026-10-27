"""Cotisations : barèmes, événements, montants dus et paiements (RG-23 à RG-26).

Les montants sont des entiers dans la devise de l'événement (le franc CFA n'a pas de
centimes). Voir docs/03-conception-detaillee.md §9.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import new_uuid, utcnow


class ContributionScale(Base):
    """Barème repris des textes de l'association : un montant par génération."""

    __tablename__ = "contribution_scale"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="XAF")
    # {"1": 50000, "2": 25000, …} : montant dû selon la génération
    amounts_by_generation: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Montant pour une génération absente du tableau (0 = rien à payer)
    default_amount: Mapped[int] = mapped_column(Integer, default=0)
    # Personnes plus jeunes que cet âge exemptées (None = pas d'exemption d'âge)
    exempt_under_age: Mapped[int | None] = mapped_column(Integer)
    # Les conjoints entrés dans la famille par alliance cotisent-ils ?
    include_spouses: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EventStatus:
    OPEN = "open"
    CLOSED = "closed"


class ContributionEvent(Base):
    """Événement à cotisation : deuil, mariage, naissance, projet, cotisation annuelle…"""

    __tablename__ = "contribution_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="other")
    description: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3), default="XAF")
    deadline: Mapped[date | None] = mapped_column(Date)
    target_amount: Mapped[int | None] = mapped_column(Integer)
    # Personne concernée (le défunt, les mariés…), facultative
    concerned_person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # Copie du barème au moment de la création (RG-24 : règles en vigueur à cette date)
    scale_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(10), default=EventStatus.OPEN)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContributionDue(Base):
    """Montant dû par une personne pour un événement (ajustable par le trésorier)."""

    __tablename__ = "contribution_due"
    __table_args__ = (UniqueConstraint("event_id", "person_id", name="uq_due_person"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contribution_event.id", ondelete="CASCADE")
    )
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"))
    amount: Mapped[int] = mapped_column(Integer)
    exempt: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(300))


class PaymentStatus:
    DECLARED = "declared"
    VALIDATED = "validated"
    REJECTED = "rejected"


class ContributionPayment(Base):
    """Paiement déclaré par un membre, compté seulement une fois validé (RG-25)."""

    __tablename__ = "contribution_payment"
    __table_args__ = (Index("ix_payment_event", "family_id", "event_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contribution_event.id", ondelete="CASCADE")
    )
    # Personne pour qui l'on paie (soi-même, un parent âgé, ses enfants…)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"))
    amount: Mapped[int] = mapped_column(Integer)
    # mobile_money, cash, bank, other
    method: Mapped[str] = mapped_column(String(20), default="mobile_money")
    reference: Mapped[str | None] = mapped_column(String(120))
    proof_url: Mapped[str | None] = mapped_column(String(500))
    # Paiement depuis la diaspora : montant et devise d'origine, pour mémoire
    original_amount: Mapped[int | None] = mapped_column(Integer)
    original_currency: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(10), default=PaymentStatus.DECLARED)
    declared_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    review_note: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
