"""Supervision de la plateforme : chiffres d'ensemble, santé, comptes, journal de l'opérateur.

Règle de confidentialité : l'opérateur voit des comptes, des compteurs et des événements
techniques, jamais le contenu d'une famille (noms des personnes, publications, récits,
montants). Les compteurs par famille sont calculés famille par famille, dans le contexte
RLS de chacune, et seuls les nombres sortent d'ici.
"""

import os
import time
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import set_family_context
from app.models import (
    AuthSession,
    Family,
    Membership,
    PlatformAudit,
    RequestMetric,
    SecurityEvent,
    User,
)
from app.security.events import client_ip

STARTED = time.time()


def audit(
    db: Session,
    operator: User,
    action: str,
    request: Request,
    target: str | None = None,
    **detail: object,
) -> None:
    """Inscrit une action de l'opérateur dans le journal de la plateforme (ajout seul)."""
    db.add(
        PlatformAudit(
            operator_id=operator.id,
            action=action,
            target=target,
            detail={k: str(v)[:300] for k, v in detail.items()},
            ip=client_ip(request),
        )
    )


def health(db: Session) -> dict:
    s = get_settings()
    bypass = db.execute(
        text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    db_ms = time.perf_counter()
    db.execute(text("SELECT 1"))
    db_ms = round((time.perf_counter() - db_ms) * 1000, 1)
    media_bytes = None
    if s.storage_backend == "local" and os.path.isdir(s.media_dir):
        media_bytes = sum(
            os.path.getsize(os.path.join(root, f))
            for root, _, files in os.walk(s.media_dir)
            for f in files
        )
    return {
        "environment": s.environment,
        "rls_enforced": not bypass,
        "migration": version,
        "database_ms": db_ms,
        "storage": s.storage_backend,
        "media_bytes": media_bytes,
        "messaging": s.messaging_backend,
        "payments": s.payment_backend,
        "rate_limit": s.rate_limit,
        "uptime_s": int(time.time() - STARTED),
    }


def overview(db: Session) -> dict:
    now = datetime.now(UTC)
    day, week = now - timedelta(days=1), now - timedelta(days=7)

    def count(query) -> int:  # noqa: ANN001
        return db.scalar(query) or 0

    events_24h = dict(
        db.execute(
            select(SecurityEvent.severity, func.count())
            .where(SecurityEvent.at >= day)
            .group_by(SecurityEvent.severity)
        ).all()
    )
    metric = db.execute(
        select(
            func.coalesce(func.sum(RequestMetric.requests), 0),
            func.coalesce(func.sum(RequestMetric.errors_4xx), 0),
            func.coalesce(func.sum(RequestMetric.errors_5xx), 0),
            func.coalesce(func.sum(RequestMetric.total_ms), 0),
            func.coalesce(func.max(RequestMetric.max_ms), 0),
        ).where(RequestMetric.minute >= day)
    ).one()
    requests = int(metric[0])
    return {
        "users": {
            "total": count(select(func.count()).select_from(User)),
            "active_7d": count(
                select(func.count()).select_from(User).where(User.last_login_at >= week)
            ),
            "new_7d": count(select(func.count()).select_from(User).where(User.created_at >= week)),
            "disabled": count(
                select(func.count()).select_from(User).where(User.is_active.is_(False))
            ),
            "locked": count(select(func.count()).select_from(User).where(User.locked_until > now)),
            "sessions": count(
                select(func.count())
                .select_from(AuthSession)
                .where(AuthSession.revoked_at.is_(None), AuthSession.expires_at > now)
            ),
        },
        "families": {
            "total": count(
                select(func.count()).select_from(Family).where(Family.merged_into_id.is_(None))
            ),
            "merged": count(
                select(func.count()).select_from(Family).where(Family.merged_into_id.is_not(None))
            ),
            "memberships": count(select(func.count()).select_from(Membership)),
        },
        "traffic_24h": {
            "requests": requests,
            "errors_4xx": int(metric[1]),
            "errors_5xx": int(metric[2]),
            "avg_ms": round(int(metric[3]) / requests, 1) if requests else 0,
            "max_ms": int(metric[4]),
        },
        "security_24h": {
            "critical": events_24h.get("critical", 0),
            "warning": events_24h.get("warning", 0),
            "info": events_24h.get("info", 0),
        },
    }


def traffic(db: Session, hours: int) -> list[dict]:
    """Trafic par tranche de 15 minutes (ou d'une heure au-delà de 48 h)."""
    step = 15 if hours <= 48 else 60
    since = datetime.now(UTC) - timedelta(hours=hours)
    buckets: dict[datetime, dict] = {}
    for m in db.scalars(
        select(RequestMetric).where(RequestMetric.minute >= since).order_by(RequestMetric.minute)
    ):
        key = m.minute.replace(minute=(m.minute.minute // step) * step if step < 60 else 0)
        b = buckets.setdefault(
            key,
            {
                "at": key,
                "requests": 0,
                "errors_4xx": 0,
                "errors_5xx": 0,
                "total_ms": 0,
                "max_ms": 0,
            },
        )
        b["requests"] += m.requests
        b["errors_4xx"] += m.errors_4xx
        b["errors_5xx"] += m.errors_5xx
        b["total_ms"] += m.total_ms
        b["max_ms"] = max(b["max_ms"], m.max_ms)
    out = []
    for b in buckets.values():
        b["avg_ms"] = round(b.pop("total_ms") / b["requests"], 1) if b["requests"] else 0
        out.append(b)
    return out


FAMILY_COUNTS = text(
    """
    SELECT (SELECT count(*) FROM person),
           (SELECT count(*) FROM post),
           (SELECT count(*) FROM narrative),
           (SELECT greatest(max(created_at), (SELECT max(created_at) FROM post)) FROM audit_log)
    """
)


def families(db: Session) -> list[dict]:
    """Une ligne par famille : identité, taille, activité. Aucun contenu."""
    members = dict(
        db.execute(select(Membership.family_id, func.count()).group_by(Membership.family_id)).all()
    )
    rows = []
    for f in db.scalars(select(Family).order_by(Family.created_at)):
        set_family_context(db, f.id)
        persons, posts, narratives, last = db.execute(FAMILY_COUNTS).one()
        rows.append(
            {
                "id": f.id,
                "name": f.name,
                "created_at": f.created_at,
                "merged": f.merged_into_id is not None,
                "members": members.get(f.id, 0),
                "persons": persons,
                "posts": posts,
                "narratives": narratives,
                "last_activity": last,
            }
        )
    set_family_context(db, None)
    return rows
