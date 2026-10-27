"""Routes de la modération : signaler, voir les signalements, les traiter."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import Ctx
from app.core.errors import bad_request, forbidden, not_found
from app.models import Comment, Post, Report, User
from app.modules.social import service
from app.modules.social.schemas import ReportIn, ReportOut

router = APIRouter(prefix="/reports", tags=["social"])


@router.post("", status_code=201)
def report(body: ReportIn, ctx: Ctx) -> dict:
    """Tout membre signale une publication ou un commentaire déplacé."""
    if bool(body.post_id) == bool(body.comment_id):
        raise bad_request("validation_error", "Indiquez une publication ou un commentaire.")
    target = (
        ctx.db.get(Post, body.post_id) if body.post_id else ctx.db.get(Comment, body.comment_id)
    )
    if target is None or target.family_id != ctx.family.id:
        raise not_found("Élément signalé")
    item = Report(family_id=ctx.family.id, reporter_id=ctx.user.id, **body.model_dump())
    ctx.db.add(item)
    ctx.db.commit()
    return {"id": str(item.id)}


@router.get("", response_model=list[ReportOut])
def open_reports(ctx: Ctx) -> list[ReportOut]:
    if not service.can_moderate(ctx):
        raise forbidden("Réservé à la modération.")
    rows = ctx.db.execute(
        select(Report, User.full_name)
        .join(User, User.id == Report.reporter_id)
        .where(Report.family_id == ctx.family.id, Report.resolved.is_(False))
        .order_by(Report.created_at.desc())
    ).all()
    out = []
    for r, name in rows:
        target = ctx.db.get(Post, r.post_id) if r.post_id else ctx.db.get(Comment, r.comment_id)
        excerpt = (target.text if target else "")[:200]
        out.append(
            ReportOut(
                id=r.id,
                post_id=r.post_id,
                comment_id=r.comment_id,
                excerpt=excerpt,
                reason=r.reason,
                reporter_name=name,
                created_at=r.created_at,
            )
        )
    return out


@router.post("/{report_id}/resolve", status_code=204)
def resolve(report_id: UUID, ctx: Ctx, hide: bool = False) -> None:
    """Clore un signalement, en masquant ou non l'élément signalé."""
    if not service.can_moderate(ctx):
        raise forbidden("Réservé à la modération.")
    item = ctx.db.get(Report, report_id)
    if item is None or item.family_id != ctx.family.id:
        raise not_found("Signalement")
    if hide:
        target = (
            ctx.db.get(Post, item.post_id) if item.post_id else ctx.db.get(Comment, item.comment_id)
        )
        if target:
            target.hidden = True
    item.resolved = True
    ctx.db.commit()
