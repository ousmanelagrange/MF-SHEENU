"""Routes des personnes : liste, fiche, création, modification, archivage, photo."""

from uuid import UUID

from fastapi import APIRouter, File, Query, UploadFile

from app.core.deps import Ctx
from app.core.errors import not_found, out_of_scope
from app.genealogy.graph import load_graph
from app.modules.persons import service
from app.modules.persons.presenters import person_detail
from app.modules.persons.schemas import (
    PersonCreate,
    PersonDetail,
    PersonList,
    PersonUpdate,
    RelativeDepth,
)
from app.shared import audit, storage

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("", response_model=PersonList)
def list_persons(
    ctx: Ctx,
    q: str | None = None,
    sort: str = Query("precedence", pattern="^(precedence|name|generation)$"),
    living: bool | None = None,
    country: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
) -> PersonList:
    graph = load_graph(ctx)
    ids = list(graph.persons)
    if country:  # carte de la diaspora : même regroupement que /diaspora
        wanted = " ".join(country.split()).casefold()
        ids = [
            pid
            for pid in ids
            if " ".join((graph.persons[pid].country or "").split()).casefold() == wanted
        ]
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
    graph = load_graph(ctx)
    anchors = service.anchors_of_new_person(body)
    for aid in anchors:
        if aid not in graph.persons:
            raise not_found("Personne liée")
    if not ctx.is_admin and not any(graph.can_write(ctx.membership, a) for a in anchors):
        raise out_of_scope()
    person = service.create_person(ctx, body)
    ctx.db.commit()
    return person_detail(ctx, load_graph(ctx), person.id)


@router.get("/{person_id}", response_model=PersonDetail)
def get_person(person_id: UUID, ctx: Ctx) -> PersonDetail:
    graph = load_graph(ctx)
    if person_id not in graph.persons:
        raise not_found("Personne")
    return person_detail(ctx, graph, person_id)


@router.patch("/{person_id}", response_model=PersonDetail)
def update_person(person_id: UUID, body: PersonUpdate, ctx: Ctx) -> PersonDetail:
    service.get_person(ctx, person_id)
    graph = load_graph(ctx)
    if not graph.can_write(ctx.membership, person_id):
        raise out_of_scope()
    service.update_person(ctx, person_id, body)
    ctx.db.commit()
    return person_detail(ctx, load_graph(ctx), person_id)


@router.delete("/{person_id}", status_code=204)
def archive_person(person_id: UUID, ctx: Ctx) -> None:
    """RG-16 : archivage, jamais de suppression physique."""
    service.get_person(ctx, person_id)
    graph = load_graph(ctx)
    if not graph.can_write(ctx.membership, person_id):
        raise out_of_scope()
    service.archive_person(ctx, person_id)
    ctx.db.commit()


@router.post("/{person_id}/photo", response_model=PersonDetail)
async def upload_photo(person_id: UUID, ctx: Ctx, file: UploadFile = File(...)) -> PersonDetail:
    p = service.get_person(ctx, person_id)
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
