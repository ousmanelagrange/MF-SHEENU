"""Mémoire de la famille : récits (audio, vidéo ou texte) avec leurs couches de transcription
et de traduction validées, et albums photo. Voir docs/03-conception-detaillee.md §11.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import new_uuid, utcnow


class Layer:
    """Couches de texte d'un récit : la transcription dans la langue du conteur, puis les traductions."""

    ORIGINAL = "original"
    FR = "fr"
    EN = "en"
    ALL = (ORIGINAL, FR, EN)


class TextStatus:
    PENDING = "pending"  # proposée, en attente de relecture
    VALIDATED = "validated"  # version de référence de la couche
    SUPERSEDED = "superseded"  # ancienne version de référence, remplacée
    REJECTED = "rejected"


class Narrative(Base):
    """Un récit : l'histoire racontée par un ancien, enregistrée ou écrite."""

    __tablename__ = "narrative"
    __table_args__ = (Index("ix_narrative_family_date", "family_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    language: Mapped[str | None] = mapped_column(String(60))  # langue du conteur, ex. « shüpamom »
    # Le conteur (souvent un ancien sans compte) et la personne qui a enregistré
    teller_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    media_url: Mapped[str | None] = mapped_column(String(500))
    media_kind: Mapped[str | None] = mapped_column(String(10))  # audio | video
    # Époque racontée : une année pour la frise, un libellé libre (« avant l'arrivée des Allemands »)
    year: Mapped[int | None] = mapped_column(Integer)
    era: Mapped[str | None] = mapped_column(String(120))
    place: Mapped[str | None] = mapped_column(String(120))
    person_ids: Mapped[list] = mapped_column(JSONB, default=list)  # personnes dont parle le récit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NarrativeText(Base):
    """Une version proposée d'une couche (transcription, traduction FR ou EN)."""

    __tablename__ = "narrative_text"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    narrative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("narrative.id", ondelete="CASCADE"))
    layer: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    status: Mapped[str] = mapped_column(String(12), default=TextStatus.PENDING)
    review_note: Mapped[str | None] = mapped_column(String(300))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Album(Base):
    __tablename__ = "album"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlbumPhoto(Base):
    __tablename__ = "album_photo"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    album_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("album.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(500))
    caption: Mapped[str | None] = mapped_column(String(300))
    year: Mapped[int | None] = mapped_column(Integer)
    person_ids: Mapped[list] = mapped_column(
        JSONB, default=list
    )  # personnes reconnues sur la photo
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
