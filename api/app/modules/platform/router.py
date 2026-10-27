"""Supervision de la plateforme (opérateur uniquement, voir service.py pour la règle de
confidentialité). Les consultations sensibles et toutes les actions sont journalisées."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select, text, update

from app.core.deps import DB, Operator
from app.core.errors import bad_request, not_found
from app.models import AuthSession, Membership, PlatformAudit, RequestMetric, SecurityEvent, User
from app.modules.platform import service
from app.security import events
from app.security.middleware import purge_idempotency

router = APIRouter(prefix="/platform", tags=["platform"])


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.get("/overview")
def overview(op: Operator, db: DB) -> dict:
    return {"health": service.health(db), **service.overview(db)}


@router.get("/traffic")
def traffic(op: Operator, db: DB, hours: int = Query(24, ge=1, le=24 * 30)) -> list[dict]:
    return service.traffic(db, hours)


@router.get("/events")
def security_events(
    op: Operator,
    db: DB,
    request: Request,
    kind: str | None = None,
    severity: str | None = None,
    user_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
    before: datetime | None = None,
) -> list[dict]:
    query = select(SecurityEvent, User.email, User.full_name).outerjoin(
        User, User.id == SecurityEvent.user_id
    )
    if kind:
        query = query.where(SecurityEvent.kind == kind)
    if severity:
        query = query.where(SecurityEvent.severity == severity)
    if user_id:
        query = query.where(SecurityEvent.user_id == user_id)
    if before:
        query = query.where(SecurityEvent.at < before)
    rows = db.execute(query.order_by(SecurityEvent.at.desc()).limit(limit)).all()
    return [
        {
            "id": e.id,
            "at": e.at,
            "kind": e.kind,
            "severity": e.severity,
            "user_id": e.user_id,
            "user": name or email,
            "ip": e.ip,
            "path": e.path,
            "detail": e.detail,
        }
        for e, email, name in rows
    ]


@router.get("/users")
def users(
    op: Operator,
    db: DB,
    request: Request,
    q: str | None = None,
    status: str | None = None,
    limit: int = Query(100, le=500),
) -> list[dict]:
    now = datetime.now(UTC)
    query = select(User)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(User.full_name.ilike(like), User.email.ilike(like), User.phone.ilike(like))
        )
    if status == "disabled":
        query = query.where(User.is_active.is_(False))
    elif status == "locked":
        query = query.where(User.locked_until > now)
    elif status == "operators":
        query = query.where(User.is_platform_admin.is_(True))
    rows = list(db.scalars(query.order_by(User.created_at.desc()).limit(limit)))
    ids = [u.id for u in rows]
    fams = dict(
        db.execute(
            select(Membership.user_id, func.count())
            .where(Membership.user_id.in_(ids))
            .group_by(Membership.user_id)
        ).all()
    )
    sessions = dict(
        db.execute(
            select(AuthSession.user_id, func.count())
            .where(
                AuthSession.user_id.in_(ids),
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
            .group_by(AuthSession.user_id)
        ).all()
    )
    service.audit(db, op, "view_users", request, q=q or "", status=status or "")
    db.commit()
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "phone": u.phone,
            "created_at": u.created_at,
            "last_login_at": u.last_login_at,
            "active": u.is_active,
            "locked_until": u.locked_until if u.locked_until and u.locked_until > now else None,
            "failed_logins": u.failed_logins,
            "operator": u.is_platform_admin,
            "families": fams.get(u.id, 0),
            "sessions": sessions.get(u.id, 0),
        }
        for u in rows
    ]


def _user(db, user_id: UUID) -> User:  # noqa: ANN001
    user = db.get(User, user_id)
    if user is None:
        raise not_found("Compte")
    return user


def _revoke(db, user: User, reason: str) -> None:  # noqa: ANN001
    user.token_version += 1
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC), revoked_reason=reason)
    )


@router.post("/users/{user_id}/disable", status_code=204)
def disable(user_id: UUID, body: ReasonIn, op: Operator, db: DB, request: Request) -> None:
    """Suspend un compte (piraté, abusif) : il ne peut plus se connecter, ses sessions tombent."""
    user = _user(db, user_id)
    if user.id == op.id:
        raise bad_request("self", "Vous ne pouvez pas suspendre votre propre compte.")
    user.is_active = False
    _revoke(db, user, "disabled_by_operator")
    service.audit(db, op, "disable_user", request, str(user.id), reason=body.reason)
    db.commit()
    events.record("account_disabled", request, user.id, by=op.id, reason=body.reason)


@router.post("/users/{user_id}/enable", status_code=204)
def enable(user_id: UUID, body: ReasonIn, op: Operator, db: DB, request: Request) -> None:
    user = _user(db, user_id)
    user.is_active, user.failed_logins, user.locked_until = True, 0, None
    service.audit(db, op, "enable_user", request, str(user.id), reason=body.reason)
    db.commit()


@router.post("/users/{user_id}/unlock", status_code=204)
def unlock(user_id: UUID, op: Operator, db: DB, request: Request) -> None:
    """Lève un verrouillage après échecs de connexion (la personne a retrouvé son mot de passe)."""
    user = _user(db, user_id)
    user.failed_logins, user.locked_until = 0, None
    service.audit(db, op, "unlock_user", request, str(user.id))
    db.commit()


@router.post("/users/{user_id}/revoke-sessions", status_code=204)
def revoke_sessions(user_id: UUID, body: ReasonIn, op: Operator, db: DB, request: Request) -> None:
    """Déconnecte le compte de tous ses appareils (téléphone perdu, soupçon de piratage)."""
    user = _user(db, user_id)
    _revoke(db, user, "revoked_by_operator")
    service.audit(db, op, "revoke_sessions", request, str(user.id), reason=body.reason)
    db.commit()


@router.get("/families")
def families(op: Operator, db: DB, request: Request) -> list[dict]:
    rows = service.families(db)
    service.audit(db, op, "view_families", request)
    db.commit()
    return rows


@router.get("/audit")
def platform_audit(op: Operator, db: DB, limit: int = Query(200, le=1000)) -> list[dict]:
    rows = db.execute(
        select(PlatformAudit, User.full_name)
        .outerjoin(User, User.id == PlatformAudit.operator_id)
        .order_by(PlatformAudit.at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": a.id,
            "at": a.at,
            "operator": name,
            "action": a.action,
            "target": a.target,
            "detail": a.detail,
            "ip": a.ip,
        }
        for a, name in rows
    ]


@router.post("/maintenance/purge")
def purge(op: Operator, db: DB, request: Request) -> dict:
    """Efface les clés d'idempotence de plus de 48 h et les compteurs de plus de 90 jours.
    Les journaux d'audit et de sécurité ne sont jamais effacés par l'application."""
    keys = purge_idempotency()
    metrics = db.execute(
        delete(RequestMetric).where(RequestMetric.minute < func.now() - text("interval '90 days'"))
    ).rowcount
    service.audit(db, op, "purge", request, idempotency=keys, metrics=metrics)
    db.commit()
    return {"idempotency_keys": keys, "metrics": metrics}
