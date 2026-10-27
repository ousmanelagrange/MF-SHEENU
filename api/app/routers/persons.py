from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, File, Query, UploadFile
from sqlalchemy import select

from app.core.errors import bad_request, forbidden, not_found, out_of_scope
from app.deps import Ctx, FamilyContext
from app.models import FamilyUnion, Membership, ParentChild, Person
from app.schemas import (
    PersonCreate,
    PersonDetail,
    PersonList,
    PersonOut,
    PersonUpdate,
    RelativeDepth,
    RelativeLink,
    SpouseLink,
)
from app.services import audit, storage
from app.services.graph import FamilyGraph

router = APIRouter(prefix="/persons", tags=["persons"])


def load_graph(ctx: FamilyContext) -> FamilyGraph:
    return FamilyGraph.load(ctx.db, ctx.family.id, ctx.family.root_person_id)


def get_person_or_404(ctx: FamilyContext, pid: UUID) -> Person:
    p = ctx.db.get(Person, pid)
    if p is None or p.family_id != ctx.family.id or p.archived_at is not None:
        raise not_found("Personne")
    return p


def contact_visible(ctx: FamilyContext, graph: FamilyGraph, p: Person) -> bool:
    """RG-21 : visibilité des coordonnées choisie par la personne."""
    if ctx.membership.person_id == p.id:
        return True
    vis = p.contact_visibility
    if vis == "family":
        return True
    if vis == "board":
        return ctx.is_board
    if vis == "branch":
        if ctx.is_board:
            return True
        mine = graph.branch_of(ctx.membership.person_id) if ctx.membership.person_id else None
        return mine is not None and mine == graph.branch_of(p.id)
    return False


def person_out(ctx: FamilyContext, graph: FamilyGraph, pid: UUID) -> PersonOut:
    p = graph.persons[pid]
    show = contact_visible(ctx, graph, p)
    return PersonOut(
        **graph.summary(pid).model_dump(),
        nickname=p.nickname,
        birth_date=p.birth_date,
        birth_place=p.birth_place,
        death_date=p.death_date,
        death_place=p.death_place,
        village=p.village,
        country=p.country,
        biography=p.biography,
        phone=p.phone if show else None,
        email=p.email if show else None,
        contact_visibility=p.contact_visibility,
        created_at=p.created_at,
        updated_at=p.updated_at,
        can_edit=graph.can_write(ctx.membership, pid),
    )


def person_detail(ctx: FamilyContext, graph: FamilyGraph, pid: UUID) -> PersonDetail:
    base = person_out(ctx, graph, pid)
    links = [link for link in graph.parent_links if pid in (link.parent_id, link.child_id)]
    parents = [
        RelativeLink(
            relation_id=link.id,
            kind=link.kind,
            certainty=link.certainty,
            person=graph.summary(link.parent_id),
        )
        for link in links
        if link.child_id == pid and link.parent_id in graph.persons
    ]
    children = [
        RelativeLink(
            relation_id=link.id,
            kind=link.kind,
            certainty=link.certainty,
            person=graph.summary(link.child_id),
        )
        for link in links
        if link.parent_id == pid and link.child_id in graph.persons
    ]
    children.sort(key=lambda r: graph.precedence_key(r.person.id)[2:])
    spouses = []
    for u in graph.unions:
        if pid not in (u.person_a_id, u.person_b_id):
            continue
        other = u.person_b_id if u.person_a_id == pid else u.person_a_id
        if other not in graph.persons:
            continue
        spouses.append(
            SpouseLink(
                union_id=u.id,
                kind=u.kind,
                rank=u.rank,
                start_date=u.start_date,
                end_date=u.end_date,
                end_reason=u.end_reason,
                person=graph.summary(other),
            )
        )
    spouses.sort(key=lambda s: (s.rank or 99, s.start_date or datetime.max.date()))
    siblings = sorted(graph.siblings(pid), key=lambda s: graph.precedence_key(s)[2:])
    return PersonDetail(
        **base.model_dump(),
        parents=parents,
        children=children,
        spouses=spouses,
        siblings=[graph.summary(s) for s in siblings],
    )


@router.get("", response_model=PersonList)
def list_persons(
    ctx: Ctx,
    q: str | None = None,
    sort: str = Query("precedence", pattern="^(precedence|name|generation)$"),
    living: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
) -> PersonList:
    graph = load_graph(ctx)
    ids = list(graph.persons)
    if q:
        needle = q.lower().strip()
        ids = [
            pid
            for pid in ids
            if needle
            in " ".join(
                x or ""
                for x in (
                    graph.persons[pid].first_name,
                    graph.persons[pid].last_name,
                    graph.persons[pid].traditional_name,
                    graph.persons[pid].nickname,
                )
            ).lower()
        ]
    if living is not None:
        ids = [pid for pid in ids if graph.persons[pid].is_living == living]
    if sort == "precedence":
        ids.sort(key=graph.precedence_key)
    elif sort == "generation":
        ids.sort(key=lambda pid: graph.precedence_key(pid)[1:])
    else:
        ids.sort(key=lambda pid: graph.precedence_key(pid)[3:])
    return PersonList(
        items=[graph.summary(pid) for pid in ids[skip : skip + limit]], total=len(ids)
    )


@router.post("", response_model=PersonDetail, status_code=201)
def create_person(body: PersonCreate, ctx: Ctx) -> PersonDetail:
    db = ctx.db
    graph = load_graph(ctx)
    anchors = [*body.parent_ids, *([body.spouse_id] if body.spouse_id else [])]
    for aid in anchors:
        if aid not in graph.persons:
            raise not_found("Personne liée")
    if not ctx.is_admin and not any(graph.can_write(ctx.membership, a) for a in anchors):
        raise out_of_scope()
    if len(set(body.parent_ids)) != len(body.parent_ids):
        raise bad_request("validation_error", "Parents en double.")

    data = body.model_dump(exclude={"parent_ids", "spouse_id", "union_kind", "union_rank"})
    person = Person(family_id=ctx.family.id, created_by=ctx.user.id, **data)
    if person.death_date or person.death_year:
        person.is_living = False
    db.add(person)
    db.flush()
    audit.record(ctx, "create", "person", person.id, after=audit.snapshot(person))
    for parent_id in body.parent_ids:
        link = ParentChild(family_id=ctx.family.id, parent_id=parent_id, child_id=person.id)
        db.add(link)
        db.flush()
        audit.record(ctx, "create", "parent_child", link.id, after=audit.snapshot(link))
    if body.spouse_id:
        u = FamilyUnion(
            family_id=ctx.family.id,
            person_a_id=body.spouse_id,
            person_b_id=person.id,
            kind=body.union_kind,
            rank=body.union_rank,
        )
        db.add(u)
        db.flush()
        audit.record(ctx, "create", "union", u.id, after=audit.snapshot(u))
    db.commit()
    graph = load_graph(ctx)
    return person_detail(ctx, graph, person.id)


@router.get("/{person_id}", response_model=PersonDetail)
def get_person(person_id: UUID, ctx: Ctx) -> PersonDetail:
    graph = load_graph(ctx)
    if person_id not in graph.persons:
        raise not_found("Personne")
    return person_detail(ctx, graph, person_id)


@router.patch("/{person_id}", response_model=PersonDetail)
def update_person(person_id: UUID, body: PersonUpdate, ctx: Ctx) -> PersonDetail:
    p = get_person_or_404(ctx, person_id)
    graph = load_graph(ctx)
    if not graph.can_write(ctx.membership, person_id):
        raise out_of_scope()
    before = audit.snapshot(p)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(p, key, value)
    if p.death_date or p.death_year:
        p.is_living = False
    p.updated_at = datetime.now(UTC)
    audit.record(ctx, "update", "person", p.id, before, audit.snapshot(p))
    ctx.db.commit()
    return person_detail(ctx, load_graph(ctx), person_id)


@router.delete("/{person_id}", status_code=204)
def archive_person(person_id: UUID, ctx: Ctx) -> None:
    """RG-16 : archivage, jamais de suppression physique."""
    p = get_person_or_404(ctx, person_id)
    graph = load_graph(ctx)
    if not graph.can_write(ctx.membership, person_id):
        raise out_of_scope()
    if ctx.family.root_person_id == person_id:
        raise bad_request("is_root", "Impossible d'archiver l'ancêtre racine.")
    if ctx.db.scalar(
        select(Membership).where(
            Membership.family_id == ctx.family.id, Membership.person_id == person_id
        )
    ):
        raise forbidden("Cette fiche est liée au compte d'un membre.")
    before = audit.snapshot(p)
    p.archived_at = datetime.now(UTC)
    audit.record(ctx, "archive", "person", p.id, before, audit.snapshot(p))
    ctx.db.commit()


@router.post("/{person_id}/photo", response_model=PersonDetail)
async def upload_photo(person_id: UUID, ctx: Ctx, file: UploadFile = File(...)) -> PersonDetail:
    p = get_person_or_404(ctx, person_id)
    graph = load_graph(ctx)
    if not graph.can_write(ctx.membership, person_id):
        raise out_of_scope()
    raw = await file.read()
    url = storage.save_photo(ctx.family.id, raw)
    before = {"photo_url": p.photo_url}
    p.photo_url = url
    audit.record(ctx, "update", "person", p.id, before, {"photo_url": url})
    ctx.db.commit()
    return person_detail(ctx, load_graph(ctx), person_id)


@router.get("/{person_id}/ancestors", response_model=list[RelativeDepth])
def ancestors(person_id: UUID, ctx: Ctx, depth: int = Query(20, ge=1, le=50)) -> list:
    graph = load_graph(ctx)
    if person_id not in graph.persons:
        raise not_found("Personne")
    items = sorted(graph.ancestors(person_id, depth).items(), key=lambda kv: kv[1])
    return [RelativeDepth(person=graph.summary(pid), depth=d) for pid, d in items]


@router.get("/{person_id}/descendants", response_model=list[RelativeDepth])
def descendants(person_id: UUID, ctx: Ctx, depth: int = Query(20, ge=1, le=50)) -> list:
    graph = load_graph(ctx)
    if person_id not in graph.persons:
        raise not_found("Personne")
    items = sorted(graph.descendants(person_id, depth).items(), key=lambda kv: kv[1])
    return [RelativeDepth(person=graph.summary(pid), depth=d) for pid, d in items]
