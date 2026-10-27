"""Tables de la plateforme (hors familles, hors RLS) : sécurité, sessions, supervision.

Aucune ne contient de contenu familial : ni noms de personnes, ni textes publiés. On y
trouve des identifiants de comptes, des adresses IP, des chemins d'API et des compteurs.
Voir docs/03-conception-detaillee.md §13.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import new_uuid, utcnow


class SecurityEvent(Base):
    """Événement de sécurité ou d'exploitation : connexion échouée, compte verrouillé,
    débit dépassé, tentative d'accès à une famille étrangère, jeton réutilisé, erreur serveur…"""

    __tablename__ = "security_event"
    __table_args__ = (
        Index("ix_security_event_at", "at"),
        Index("ix_security_event_kind", "kind", "at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    kind: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10), default="info")  # info | warning | critical
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    path: Mapped[str | None] = mapped_column(String(300))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)


class AuthSession(Base):
    """Une session d'appareil : chaque jeton de rafraîchissement en porte l'identifiant.

    À chaque rafraîchissement, la session reçoit un nouveau numéro de rotation ; un jeton
    plus ancien présenté à nouveau signale un vol : toutes les sessions du compte tombent."""

    __tablename__ = "auth_session"
    __table_args__ = (Index("ix_auth_session_user", "user_id", "revoked_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    rotation: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(40))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))


class IdempotencyKey(Base):
    """Réponse mémorisée d'une écriture envoyée avec l'en-tête Idempotency-Key : un envoi
    rejoué (application hors ligne qui resynchronise, double appui) n'est appliqué qu'une fois."""

    __tablename__ = "idempotency_key"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer, default=0)  # 0 : en cours de traitement
    response_body: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RequestMetric(Base):
    """Compteurs de requêtes par minute (agrégés par chaque processus de l'API)."""

    __tablename__ = "request_metric"

    minute: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    errors_4xx: Mapped[int] = mapped_column(Integer, default=0)
    errors_5xx: Mapped[int] = mapped_column(Integer, default=0)
    total_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    max_ms: Mapped[int] = mapped_column(Integer, default=0)


class PlatformAudit(Base):
    """Journal des actions de l'opérateur de la plateforme (supervision)."""

    __tablename__ = "platform_audit"
    __table_args__ = (Index("ix_platform_audit_at", "at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    operator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(
        String(40)
    )  # ex. disable_user, revoke_sessions, view_events
    target: Mapped[str | None] = mapped_column(String(120))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64))
