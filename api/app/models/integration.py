"""Phase 6 — intégrations : notifications, demandes de rattachement, paiements en ligne.
Voir docs/03-conception-detaillee.md §12.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import new_uuid, utcnow


class Notification(Base):
    """Message adressé à un membre dans une famille (cloche de l'application)."""

    __tablename__ = "notification"
    __table_args__ = (Index("ix_notification_user", "user_id", "family_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))  # ex. announcement, comment, payment_validated
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))  # chemin de l'application web, ex. /fil
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JoinLink(Base):
    """Lien de rattachement d'une famille, réutilisable, à poster dans le groupe WhatsApp.

    Hors RLS : il est lu avant de connaître la famille, comme une invitation. Seule
    l'empreinte du jeton est stockée ; régénérer le lien invalide l'ancien."""

    __tablename__ = "join_link"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("family.id", ondelete="CASCADE"), unique=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JoinStatus:
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class JoinRequest(Base):
    """Demande d'une personne qui se reconnaît de la famille et veut y être rattachée."""

    __tablename__ = "join_request"
    __table_args__ = (UniqueConstraint("family_id", "user_id", name="uq_join_request_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    sex: Mapped[str] = mapped_column(String(1), default="U")
    birth_year: Mapped[int | None] = mapped_column(Integer)
    # Comment la personne se situe : « fils d'Issa Nchare, petit-fils de Mfon Adamou »
    lineage: Mapped[str] = mapped_column(Text)
    village: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(10), default=JoinStatus.PENDING)
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # fiche attribuée
    review_note: Mapped[str | None] = mapped_column(String(300))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PaymentIntent(Base):
    """Paiement Mobile Money lancé chez un prestataire, en attente de sa confirmation.

    Hors RLS : le webhook du prestataire arrive sans famille ; cette table lui permet de
    retrouver la famille et le paiement avant d'ouvrir le contexte RLS."""

    __tablename__ = "payment_intent"
    __table_args__ = (UniqueConstraint("provider", "provider_ref", name="uq_payment_intent_ref"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    provider: Mapped[str] = mapped_column(String(20))
    provider_ref: Mapped[str] = mapped_column(String(120))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | success | failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
