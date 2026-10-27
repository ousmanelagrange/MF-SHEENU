"""Proposition de modification de l'arbre, soumise à validation (RG-13, RG-14).

Un membre qui veut modifier une partie de l'arbre hors de son périmètre envoie une
proposition. Le chef de branche concerné, ou le bureau, l'accepte (le changement est
alors appliqué) ou la refuse avec un motif.

Voir docs/03-conception-detaillee.md §8.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import new_uuid, utcnow


class ProposalStatus:
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Proposal(Base):
    __tablename__ = "proposal"
    __table_args__ = (Index("ix_proposal_family_status", "family_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    # Type d'opération : create_person, update_person, archive_person, add_parent_child,
    # add_union, delete_parent_child, delete_union.
    kind: Mapped[str] = mapped_column(String(30))
    # Données de l'opération, validées par le schéma correspondant au type.
    payload: Mapped[dict] = mapped_column(JSONB)
    # Personnes concernées : elles déterminent qui peut valider.
    anchor_ids: Mapped[list] = mapped_column(JSONB, default=list)
    # Phrase lisible, figée à la création (« Ajouter Awa comme enfant de Moussa »).
    summary: Mapped[str] = mapped_column(String(300))
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default=ProposalStatus.PENDING)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    review_note: Mapped[str | None] = mapped_column(Text)
    result_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
