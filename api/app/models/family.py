"""Espace familial et appartenance d'un compte à une famille.

Voir docs/03-conception-detaillee.md §1."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import new_uuid, utcnow


class Role:
    MEMBER = "member"
    BRANCH_HEAD = "branch_head"
    TREASURER = "treasurer"
    SECRETARY = "secretary"
    ADMIN = "admin"
    ALL = (MEMBER, BRANCH_HEAD, TREASURER, SECRETARY, ADMIN)


class Family(Base):
    __tablename__ = "family"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200))
    community: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    # Pas de FK stricte vers person : la racine est créée après la famille et la RLS
    # rendrait la vérification dépendante du contexte. Le service garantit la cohérence.
    root_person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # Famille réunie à une autre : elle disparaît des listes et n'est plus accessible.
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Incrémenté par la base à chaque changement de l'arbre (déclencheurs, migration 0009) :
    # sert à savoir si l'arbre gardé en mémoire est encore à jour.
    graph_version: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")


class Membership(Base):
    __tablename__ = "membership"
    __table_args__ = (
        UniqueConstraint("family_id", "user_id", name="uq_membership_user"),
        UniqueConstraint("family_id", "person_id", name="uq_membership_person"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    role: Mapped[str] = mapped_column(String(20), default=Role.MEMBER)
    status: Mapped[str] = mapped_column(String(20), default="active")
    branch_person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
