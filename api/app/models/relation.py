"""Liens entre personnes : filiation (parent → enfant) et union.

Voir docs/03-conception-detaillee.md §1."""

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import new_uuid


class ParentChild(Base):
    __tablename__ = "parent_child"
    __table_args__ = (
        UniqueConstraint("parent_id", "child_id", name="uq_parent_child"),
        CheckConstraint("parent_id <> child_id", name="ck_parent_not_child"),
        Index("ix_pc_parent", "family_id", "parent_id"),
        Index("ix_pc_child", "family_id", "child_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    parent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"))
    child_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(12), default="biological")
    certainty: Mapped[str] = mapped_column(String(12), default="documented")
    source: Mapped[str | None] = mapped_column(Text)


class FamilyUnion(Base):
    __tablename__ = "family_union"
    __table_args__ = (
        UniqueConstraint("person_a_id", "person_b_id", "kind", name="uq_union"),
        CheckConstraint("person_a_id <> person_b_id", name="ck_union_distinct"),
        Index("ix_union_a", "family_id", "person_a_id"),
        Index("ix_union_b", "family_id", "person_b_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    person_a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"))
    person_b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(12), default="customary")
    rank: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    end_reason: Mapped[str | None] = mapped_column(String(12))
    certainty: Mapped[str] = mapped_column(String(12), default="documented")
