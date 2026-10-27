"""Vie sociale de la famille : publications, stories, commentaires, réactions, sondages,
signalements et messages de mémorial. Voir docs/03-conception-detaillee.md §10.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import new_uuid, utcnow


class PostKind:
    POST = "post"  # publication ordinaire
    ANNOUNCEMENT = "announcement"  # annonce officielle du bureau
    LIFE_EVENT = "life_event"  # naissance, mariage, décès, réussite…
    POLL = "poll"  # sondage


class Post(Base):
    __tablename__ = "post"
    __table_args__ = (Index("ix_post_family_date", "family_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    # Publié au nom d'une personne déléguée (un ancien sans smartphone), facultatif
    on_behalf_of: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(15), default=PostKind.POST)
    # Pour une annonce de vie : birth, wedding, death, success, other
    life_event: Mapped[str | None] = mapped_column(String(15))
    text: Mapped[str] = mapped_column(Text, default="")
    media: Mapped[list] = mapped_column(JSONB, default=list)  # adresses des photos
    person_ids: Mapped[list] = mapped_column(JSONB, default=list)  # personnes citées ou identifiées
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)  # masquée par la modération
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PollOption(Base):
    __tablename__ = "poll_option"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("post.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)


class PollVote(Base):
    """Un vote par membre et par sondage (on peut changer d'avis)."""

    __tablename__ = "poll_vote"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_poll_vote"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("post.id", ondelete="CASCADE"))
    option_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("poll_option.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))


class Comment(Base):
    __tablename__ = "comment"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("post.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    text: Mapped[str] = mapped_column(Text)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Reaction(Base):
    """Une réaction par membre et par publication."""

    __tablename__ = "reaction"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_reaction"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("post.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    emoji: Mapped[str] = mapped_column(String(10))  # like, love, pray, clap


class Story(Base):
    """Photo éphémère, visible 24 heures."""

    __tablename__ = "story"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    media_url: Mapped[str] = mapped_column(String(500))
    caption: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Report(Base):
    """Signalement d'une publication ou d'un commentaire, traité par la modération."""

    __tablename__ = "report"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("post.id", ondelete="CASCADE"))
    comment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comment.id", ondelete="CASCADE")
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    reason: Mapped[str] = mapped_column(String(300))
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MemorialMessage(Base):
    """Hommage ou condoléances sur la page mémorial d'une personne décédée."""

    __tablename__ = "memorial_message"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"))
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
