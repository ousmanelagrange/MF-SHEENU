"""Route du journal d'audit, réservée aux administrateurs (RG-15)."""

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.deps import AdminCtx
from app.models import AuditLog, User
from app.modules.audit.schemas import AuditList, AuditOut

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=AuditList)
def list_audit(
    ctx: AdminCtx,
    entity: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> AuditList:
    base = select(AuditLog).where(AuditLog.family_id == ctx.family.id)
    if entity:
        base = base.where(AuditLog.entity == entity)
    total = ctx.db.scalar(select(func.count()).select_from(base.subquery()))
    rows = ctx.db.execute(
        base.add_columns(User.full_name)
        .outerjoin(User, User.id == AuditLog.user_id)
        .order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    items = []
    for log, name in rows:
        out = AuditOut.model_validate(log)
        out.user_name = name
        items.append(out)
    return AuditList(items=items, total=total)
