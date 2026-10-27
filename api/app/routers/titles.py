from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.core.errors import conflict, not_found
from app.deps import AdminCtx, Ctx
from app.models import Person, TitleDefinition, TitleHolding
from app.schemas import (
    TitleCreate,
    TitleHoldingCreate,
    TitleHoldingOut,
    TitleHoldingUpdate,
    TitleOut,
    TitleUpdate,
)
from app.services import audit

router = APIRouter(tags=["titles"])


@router.get("/titles", response_model=list[TitleOut])
def list_titles(ctx: Ctx) -> list[TitleDefinition]:
    return list(
        ctx.db.scalars(
            select(TitleDefinition)
            .where(TitleDefinition.family_id == ctx.family.id)
            .order_by(TitleDefinition.precedence, TitleDefinition.name)
        )
    )


@router.post("/titles", response_model=TitleOut, status_code=201)
def create_title(body: TitleCreate, ctx: AdminCtx) -> TitleDefinition:
    if ctx.db.scalar(
        select(TitleDefinition).where(
            TitleDefinition.family_id == ctx.family.id, TitleDefinition.name == body.name
        )
    ):
        raise conflict("already_exists", "Ce titre existe déjà.")
    t = TitleDefinition(family_id=ctx.family.id, **body.model_dump())
    ctx.db.add(t)
    ctx.db.flush()
    audit.record(ctx, "create", "title", t.id, after=audit.snapshot(t))
    ctx.db.commit()
    return t


def _get_title(ctx, title_id: UUID) -> TitleDefinition:  # noqa: ANN001
    t = ctx.db.get(TitleDefinition, title_id)
    if t is None or t.family_id != ctx.family.id:
        raise not_found("Titre")
    return t


@router.patch("/titles/{title_id}", response_model=TitleOut)
def update_title(title_id: UUID, body: TitleUpdate, ctx: AdminCtx) -> TitleDefinition:
    t = _get_title(ctx, title_id)
    before = audit.snapshot(t)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(t, key, value)
    audit.record(ctx, "update", "title", t.id, before, audit.snapshot(t))
    ctx.db.commit()
    return t


@router.delete("/titles/{title_id}", status_code=204)
def delete_title(title_id: UUID, ctx: AdminCtx) -> None:
    t = _get_title(ctx, title_id)
    audit.record(ctx, "delete", "title", t.id, before=audit.snapshot(t))
    ctx.db.delete(t)
    ctx.db.commit()


@router.get("/persons/{person_id}/titles", response_model=list[TitleHoldingOut])
def person_titles(person_id: UUID, ctx: Ctx) -> list[TitleHolding]:
    return list(
        ctx.db.scalars(
            select(TitleHolding)
            .where(TitleHolding.family_id == ctx.family.id, TitleHolding.person_id == person_id)
            .order_by(TitleHolding.conferred_on)
        )
    )


@router.post("/persons/{person_id}/titles", response_model=TitleHoldingOut, status_code=201)
def grant_title(person_id: UUID, body: TitleHoldingCreate, ctx: AdminCtx) -> TitleHolding:
    p = ctx.db.get(Person, person_id)
    if p is None or p.family_id != ctx.family.id or p.archived_at:
        raise not_found("Personne")
    _get_title(ctx, body.title_id)
    h = TitleHolding(family_id=ctx.family.id, person_id=person_id, **body.model_dump())
    ctx.db.add(h)
    ctx.db.flush()
    audit.record(ctx, "create", "title_holding", h.id, after=audit.snapshot(h))
    ctx.db.commit()
    return h


def _get_holding(ctx, holding_id: UUID) -> TitleHolding:  # noqa: ANN001
    h = ctx.db.get(TitleHolding, holding_id)
    if h is None or h.family_id != ctx.family.id:
        raise not_found("Détention de titre")
    return h


@router.patch("/title-holdings/{holding_id}", response_model=TitleHoldingOut)
def update_holding(holding_id: UUID, body: TitleHoldingUpdate, ctx: AdminCtx) -> TitleHolding:
    h = _get_holding(ctx, holding_id)
    before = audit.snapshot(h)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(h, key, value)
    audit.record(ctx, "update", "title_holding", h.id, before, audit.snapshot(h))
    ctx.db.commit()
    return h


@router.delete("/title-holdings/{holding_id}", status_code=204)
def delete_holding(holding_id: UUID, ctx: AdminCtx) -> None:
    h = _get_holding(ctx, holding_id)
    audit.record(ctx, "delete", "title_holding", h.id, before=audit.snapshot(h))
    ctx.db.delete(h)
    ctx.db.commit()
