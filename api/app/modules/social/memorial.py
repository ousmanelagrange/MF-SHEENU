"""Routes du mémorial (hommages aux défunts) et des anniversaires à venir."""

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import Ctx
from app.core.errors import bad_request, forbidden, not_found
from app.genealogy.graph import load_graph
from app.models import MemorialMessage
from app.modules.social import service
from app.modules.social.schemas import Birthday, MemorialIn, MemorialOut

router = APIRouter(tags=["social"])


@router.get("/persons/{person_id}/memorial", response_model=list[MemorialOut])
def memorial(person_id: UUID, ctx: Ctx) -> list[MemorialOut]:
    messages = list(
        ctx.db.scalars(
            select(MemorialMessage)
            .where(
                MemorialMessage.family_id == ctx.family.id, MemorialMessage.person_id == person_id
            )
            .order_by(MemorialMessage.created_at.desc())
        )
    )
    people = service.authors(ctx, load_graph(ctx), {m.author_id for m in messages})
    moderator = service.can_moderate(ctx)
    return [
        MemorialOut(
            id=m.id,
            author=people[m.author_id],
            text=m.text,
            created_at=m.created_at,
            can_delete=moderator or m.author_id == ctx.user.id,
        )
        for m in messages
    ]


@router.post("/persons/{person_id}/memorial", response_model=MemorialOut, status_code=201)
def add_tribute(person_id: UUID, body: MemorialIn, ctx: Ctx) -> MemorialOut:
    """Un hommage ne se laisse que sur la page d'une personne décédée."""
    graph = load_graph(ctx)
    if person_id not in graph.persons:
        raise not_found("Personne")
    if graph.persons[person_id].is_living:
        raise bad_request("not_deceased", "Le mémorial est réservé aux personnes décédées.")
    message = MemorialMessage(
        family_id=ctx.family.id, person_id=person_id, author_id=ctx.user.id, text=body.text.strip()
    )
    ctx.db.add(message)
    ctx.db.commit()
    author = service.authors(ctx, graph, {ctx.user.id})[ctx.user.id]
    return MemorialOut(
        id=message.id,
        author=author,
        text=message.text,
        created_at=message.created_at,
        can_delete=True,
    )


@router.delete("/memorial/{message_id}", status_code=204)
def delete_tribute(message_id: UUID, ctx: Ctx) -> None:
    message = ctx.db.get(MemorialMessage, message_id)
    if message is None or message.family_id != ctx.family.id:
        raise not_found("Hommage")
    if message.author_id != ctx.user.id and not service.can_moderate(ctx):
        raise forbidden()
    ctx.db.delete(message)
    ctx.db.commit()


def next_occurrence(birth: date, today: date) -> date:
    """Prochaine date anniversaire (le 29 février est fêté le 28 les années non bissextiles)."""
    for year in (today.year, today.year + 1):
        try:
            candidate = birth.replace(year=year)
        except ValueError:
            candidate = date(year, 2, 28)
        if candidate >= today:
            return candidate
    return today


@router.get("/birthdays", response_model=list[Birthday])
def birthdays(ctx: Ctx, days: int = Query(30, ge=1, le=366)) -> list[Birthday]:
    """Anniversaires des personnes vivantes dans les `days` prochains jours (date complète connue)."""
    graph = load_graph(ctx)
    today = date.today()
    horizon = today + timedelta(days=days)
    out = []
    for pid, p in graph.persons.items():
        if not p.is_living or not p.birth_date:
            continue
        when = next_occurrence(p.birth_date, today)
        if when <= horizon:
            out.append(
                Birthday(
                    person=graph.summary(pid),
                    date=when,
                    age=when.year - p.birth_date.year,
                    in_days=(when - today).days,
                )
            )
    return sorted(out, key=lambda b: b.in_days)
