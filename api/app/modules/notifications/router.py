"""Notifications du membre dans la famille courante : liste et marquage comme lues."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select, update

from app.core.deps import Ctx
from app.models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: UUID
    kind: str
    title: str
    body: str | None
    link: str | None
    read: bool
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    unread: int


class ReadIn(BaseModel):
    ids: list[UUID] | None = None  # aucune liste : tout marquer comme lu


def _mine(ctx):  # noqa: ANN001, ANN202
    return (Notification.family_id == ctx.family.id, Notification.user_id == ctx.user.id)


@router.get("", response_model=NotificationPage)
def list_notifications(ctx: Ctx, limit: int = 40) -> NotificationPage:
    rows = ctx.db.scalars(
        select(Notification)
        .where(*_mine(ctx))
        .order_by(Notification.created_at.desc())
        .limit(min(limit, 100))
    )
    unread = ctx.db.scalar(select(func.count()).where(*_mine(ctx), Notification.read_at.is_(None)))
    return NotificationPage(
        items=[
            NotificationOut(
                id=n.id,
                kind=n.kind,
                title=n.title,
                body=n.body,
                link=n.link,
                read=n.read_at is not None,
                created_at=n.created_at,
            )
            for n in rows
        ],
        unread=unread or 0,
    )


@router.post("/read", status_code=204)
def mark_read(body: ReadIn, ctx: Ctx) -> None:
    query = update(Notification).where(*_mine(ctx), Notification.read_at.is_(None))
    if body.ids is not None:
        query = query.where(Notification.id.in_(body.ids))
    ctx.db.execute(query.values(read_at=datetime.now(UTC)))
    ctx.db.commit()
