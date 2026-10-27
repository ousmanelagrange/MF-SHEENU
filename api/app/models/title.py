"""Titres traditionnels et leurs détenteurs successifs.

Voir docs/03-conception-detaillee.md §1."""

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import new_uuid


class TitleDefinition(Base):
    __tablename__ = "title_definition"
    __table_args__ = (UniqueConstraint("family_id", "name", name="uq_title_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    abbreviation: Mapped[str | None] = mapped_column(String(20))
    precedence: Mapped[int] = mapped_column(Integer, default=100)
    badge_color: Mapped[str] = mapped_column(String(16), default="#B8860B")
    hereditary: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)


class TitleHolding(Base):
    __tablename__ = "title_holding"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    title_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("title_definition.id", ondelete="CASCADE")
    )
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"))
    conferred_by: Mapped[str | None] = mapped_column(String(200))
    conferred_on: Mapped[date | None] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date)
    predecessor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("person.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
