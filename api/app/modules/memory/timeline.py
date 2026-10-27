"""Frise chronologique : naissances, unions, décès, récits, albums et annonces de vie,
pour toute la famille ou autour d'une personne."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import Ctx
from app.core.errors import not_found
from app.genealogy.graph import FamilyGraph, load_graph
from app.models import Album, AlbumPhoto, Narrative, Person, Post, PostKind
from app.modules.memory.schemas import TimelineItem

router = APIRouter(tags=["memory"])

LIFE_EVENTS = {
    "birth": "Naissance",
    "wedding": "Mariage",
    "death": "Décès",
    "success": "Réussite",
    "other": "Événement",
}


def _year(p: Person, kind: str) -> int | None:
    if kind == "birth":
        return p.birth_date.year if p.birth_date else p.birth_year
    return p.death_date.year if p.death_date else p.death_year


def person_events(graph: FamilyGraph, pid: UUID, title_prefix: str = "") -> list[TimelineItem]:
    """Naissance et décès d'une personne, quand l'année est connue."""
    p = graph.persons[pid]
    items = []
    for kind, verb in (("birth", "Naissance de"), ("death", "Décès de")):
        year = _year(p, kind)
        if year:
            when = p.birth_date if kind == "birth" else p.death_date
            items.append(
                TimelineItem(
                    year=year,
                    day=when,
                    kind=kind,
                    title=f"{title_prefix}{verb} {graph.display_name(pid)}",
                    person=graph.summary(pid),
                    ref_id=pid,
                )
            )
    return items


@router.get("/timeline", response_model=list[TimelineItem])
def timeline(ctx: Ctx, person_id: UUID | None = None) -> list[TimelineItem]:
    """Événements datés, du plus ancien au plus récent.

    Sans `person_id` : toute la famille. Avec : la personne, ses unions, la naissance de ses
    enfants, les récits et photos qui la concernent, et les annonces de vie qui la citent."""
    graph = load_graph(ctx)
    if person_id and person_id not in graph.persons:
        raise not_found("Personne")
    items: list[TimelineItem] = []

    # Personnes : toutes, ou la personne et ses enfants
    if person_id:
        items += person_events(graph, person_id)
        for child in graph.children[person_id]:
            items += [e for e in person_events(graph, child) if e.kind == "birth"]
    else:
        for pid in graph.persons:
            items += person_events(graph, pid)

    # Unions datées
    for u in graph.unions:
        if not u.start_date or (person_id and person_id not in (u.person_a_id, u.person_b_id)):
            continue
        if u.person_a_id in graph.persons and u.person_b_id in graph.persons:
            items.append(
                TimelineItem(
                    year=u.start_date.year,
                    day=u.start_date,
                    kind="union",
                    title=f"Union de {graph.display_name(u.person_a_id)} "
                    f"et {graph.display_name(u.person_b_id)}",
                    ref_id=u.person_a_id,
                )
            )

    # Récits situés dans le temps
    narratives = select(Narrative).where(
        Narrative.family_id == ctx.family.id, Narrative.year.is_not(None)
    )
    for n in ctx.db.scalars(narratives):
        if person_id and person_id != n.teller_id and str(person_id) not in n.person_ids:
            continue
        items.append(TimelineItem(year=n.year, kind="narrative", title=n.title, ref_id=n.id))

    # Albums (famille) ou photos où la personne est reconnue
    if person_id:
        photos = select(AlbumPhoto).where(
            AlbumPhoto.family_id == ctx.family.id,
            AlbumPhoto.year.is_not(None),
            AlbumPhoto.person_ids.contains([str(person_id)]),
        )
        for ph in ctx.db.scalars(photos):
            items.append(
                TimelineItem(
                    year=ph.year, kind="photo", title=ph.caption or "Photo", ref_id=ph.album_id
                )
            )
    else:
        albums = select(Album).where(Album.family_id == ctx.family.id, Album.year.is_not(None))
        for a in ctx.db.scalars(albums):
            items.append(TimelineItem(year=a.year, kind="album", title=a.title, ref_id=a.id))

    # Annonces de vie publiées dans le fil
    posts = select(Post).where(
        Post.family_id == ctx.family.id,
        Post.kind == PostKind.LIFE_EVENT,
        Post.hidden.is_(False),
    )
    for post in ctx.db.scalars(posts):
        if person_id and str(person_id) not in post.person_ids:
            continue
        label = LIFE_EVENTS.get(post.life_event or "other", "Événement")
        excerpt = post.text if len(post.text) <= 80 else post.text[:77] + "…"
        items.append(
            TimelineItem(
                year=post.created_at.year,
                day=post.created_at.date(),
                kind="life_event",
                title=f"{label} : {excerpt}",
                ref_id=post.id,
            )
        )

    items.sort(key=lambda i: (i.year, i.day.isoformat() if i.day else ""))
    return items
