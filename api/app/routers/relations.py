from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.core.errors import bad_request, conflict, not_found, out_of_scope
from app.deps import Ctx, FamilyContext
from app.models import FamilyUnion, ParentChild
from app.routers.persons import load_graph
from app.schemas import (
    ParentChildCreate,
    ParentChildOut,
    ParentChildUpdate,
    UnionCreate,
    UnionOut,
    UnionUpdate,
)
from app.services import audit
from app.services.graph import FamilyGraph

router = APIRouter(tags=["relations"])


def _require_any_scope(ctx: FamilyContext, graph: FamilyGraph, *pids: UUID) -> None:
    for pid in pids:
        if pid not in graph.persons:
            raise not_found("Personne")
    if not any(graph.can_write(ctx.membership, pid) for pid in pids):
        raise out_of_scope()


@router.post("/relations/parent-child", response_model=ParentChildOut, status_code=201)
def add_parent_child(body: ParentChildCreate, ctx: Ctx) -> ParentChild:
    graph = load_graph(ctx)
    _require_any_scope(ctx, graph, body.parent_id, body.child_id)
    if body.parent_id == body.child_id:
        raise bad_request("validation_error", "Une personne ne peut pas être son propre parent.")
    # RG-09 : pas de cycle — le parent ne doit pas descendre de l'enfant.
    if graph.is_descendant(body.parent_id, body.child_id):
        raise conflict("cycle_detected", "Ce lien créerait une boucle dans l'arbre.")
    existing = ctx.db.scalar(
        select(ParentChild).where(
            ParentChild.parent_id == body.parent_id, ParentChild.child_id == body.child_id
        )
    )
    if existing:
        raise conflict("already_exists", "Ce lien existe déjà.")
    # RG-08 : au plus deux parents biologiques.
    if body.kind == "biological":
        bio = [
            link
            for link in graph.parent_links
            if link.child_id == body.child_id and link.kind == "biological"
        ]
        if len(bio) >= 2:
            raise conflict("too_many_parents", "Cette personne a déjà deux parents biologiques.")
    link = ParentChild(family_id=ctx.family.id, **body.model_dump())
    ctx.db.add(link)
    ctx.db.flush()
    audit.record(ctx, "create", "parent_child", link.id, after=audit.snapshot(link))
    ctx.db.commit()
    return link


def _get_link(ctx: FamilyContext, link_id: UUID) -> ParentChild:
    link = ctx.db.get(ParentChild, link_id)
    if link is None or link.family_id != ctx.family.id:
        raise not_found("Lien")
    return link


@router.patch("/relations/parent-child/{link_id}", response_model=ParentChildOut)
def update_parent_child(link_id: UUID, body: ParentChildUpdate, ctx: Ctx) -> ParentChild:
    link = _get_link(ctx, link_id)
    graph = load_graph(ctx)
    _require_any_scope(ctx, graph, link.parent_id, link.child_id)
    before = audit.snapshot(link)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(link, key, value)
    audit.record(ctx, "update", "parent_child", link.id, before, audit.snapshot(link))
    ctx.db.commit()
    return link


@router.delete("/relations/parent-child/{link_id}", status_code=204)
def delete_parent_child(link_id: UUID, ctx: Ctx) -> None:
    link = _get_link(ctx, link_id)
    graph = load_graph(ctx)
    _require_any_scope(ctx, graph, link.parent_id, link.child_id)
    audit.record(ctx, "delete", "parent_child", link.id, before=audit.snapshot(link))
    ctx.db.delete(link)
    ctx.db.commit()


@router.post("/unions", response_model=UnionOut, status_code=201)
def add_union(body: UnionCreate, ctx: Ctx) -> FamilyUnion:
    if body.person_a_id == body.person_b_id:
        raise bad_request("validation_error", "Une union relie deux personnes distinctes.")
    graph = load_graph(ctx)
    _require_any_scope(ctx, graph, body.person_a_id, body.person_b_id)
    if body.person_b_id in graph.spouses.get(body.person_a_id, set()):
        raise conflict("already_exists", "Ces deux personnes sont déjà unies.")
    u = FamilyUnion(family_id=ctx.family.id, **body.model_dump())
    ctx.db.add(u)
    ctx.db.flush()
    audit.record(ctx, "create", "union", u.id, after=audit.snapshot(u))
    ctx.db.commit()
    return u


def _get_union(ctx: FamilyContext, union_id: UUID) -> FamilyUnion:
    u = ctx.db.get(FamilyUnion, union_id)
    if u is None or u.family_id != ctx.family.id:
        raise not_found("Union")
    return u


@router.patch("/unions/{union_id}", response_model=UnionOut)
def update_union(union_id: UUID, body: UnionUpdate, ctx: Ctx) -> FamilyUnion:
    u = _get_union(ctx, union_id)
    graph = load_graph(ctx)
    _require_any_scope(ctx, graph, u.person_a_id, u.person_b_id)
    before = audit.snapshot(u)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(u, key, value)
    audit.record(ctx, "update", "union", u.id, before, audit.snapshot(u))
    ctx.db.commit()
    return u


@router.delete("/unions/{union_id}", status_code=204)
def delete_union(union_id: UUID, ctx: Ctx) -> None:
    u = _get_union(ctx, union_id)
    graph = load_graph(ctx)
    _require_any_scope(ctx, graph, u.person_a_id, u.person_b_id)
    audit.record(ctx, "delete", "union", u.id, before=audit.snapshot(u))
    ctx.db.delete(u)
    ctx.db.commit()
