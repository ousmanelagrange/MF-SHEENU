"""Demande de réunion de deux familles : l'une (source) rejoint l'autre (accueil).

L'administrateur de la famille d'accueil crée un code ; l'administrateur de la famille
source l'accepte. Les deux responsables sont donc d'accord. Table hors RLS : elle relie
deux familles, et l'application vérifie les droits de chaque côté.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import new_uuid, utcnow


class FamilyMerge(Base):
    __tablename__ = "family_merge"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    target_family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    source_family_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("family.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    summary: Mapped[dict | None] = mapped_column(JSONB)
