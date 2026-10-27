"""Routes des liens : filiations et unions. Le périmètre est vérifié ici, la logique est dans service.py."""

from uuid import UUID

from fastapi import APIRouter

from app.core.deps import Ctx, FamilyContext
from app.core.errors import not_found, out_of_scope
from app.genealogy.graph import FamilyGraph, load_graph
from app.models import FamilyUnion, ParentChild
from app.modules.relations import service
from app.modules.relations.schemas import (
    ParentChildCreate,
    ParentChildOut,
    ParentChildUpdate,
    UnionCreate,
    UnionOut,
    UnionUpdate,
)
from app.shared import audit

router = APIRouter(tags=["relations"])


def require_any_scope(ctx: FamilyContext, graph: FamilyGraph, *pids: UUID) -> None:
    for pid in pids:
        if pid not in graph.persons:
            raise not_found("Personne")
    if not any(graph.can_write(ctx.membership, pid) for pid in pids):
        raise out_of_scope()


@router.post("/relations/parent-child", response_model=ParentChildOut, status_code=201)
def add_parent_child(body: ParentChildCreate, ctx: Ctx) -> ParentChild:
    require_any_scope(ctx, load_graph(ctx), body.parent_id, body.child_id)
    link = service.add_parent_child(ctx, body)
    ctx.db.commit()
    return link


@router.patch("/relations/parent-child/{link_id}", response_model=ParentChildOut)
def update_parent_child(link_id: UUID, body: ParentChildUpdate, ctx: Ctx) -> ParentChild:
    link = service.get_link(ctx, link_id)
    require_any_scope(ctx, load_graph(ctx), link.parent_id, link.child_id)
    before = audit.snapshot(link)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(link, key, value)
    audit.record(ctx, "update", "parent_child", link.id, before, audit.snapshot(link))
    ctx.db.commit()
    return link


@router.delete("/relations/parent-child/{link_id}", status_code=204)
def delete_parent_child(link_id: UUID, ctx: Ctx) -> None:
    link = service.get_link(ctx, link_id)
    require_any_scope(ctx, load_graph(ctx), link.parent_id, link.child_id)
    service.delete_parent_child(ctx, link_id)
    ctx.db.commit()


@router.post("/unions", response_model=UnionOut, status_code=201)
def add_union(body: UnionCreate, ctx: Ctx) -> FamilyUnion:
    graph = load_graph(ctx)
    if body.person_a_id != body.person_b_id:
        require_any_scope(ctx, graph, body.person_a_id, body.person_b_id)
    u = service.add_union(ctx, body)
    ctx.db.commit()
    return u


@router.patch("/unions/{union_id}", response_model=UnionOut)
def update_union(union_id: UUID, body: UnionUpdate, ctx: Ctx) -> FamilyUnion:
    u = service.get_union(ctx, union_id)
    require_any_scope(ctx, load_graph(ctx), u.person_a_id, u.person_b_id)
    before = audit.snapshot(u)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(u, key, value)
    audit.record(ctx, "update", "union", u.id, before, audit.snapshot(u))
    ctx.db.commit()
    return u


@router.delete("/unions/{union_id}", status_code=204)
def delete_union(union_id: UUID, ctx: Ctx) -> None:
    u = service.get_union(ctx, union_id)
    require_any_scope(ctx, load_graph(ctx), u.person_a_id, u.person_b_id)
    service.delete_union(ctx, union_id)
    ctx.db.commit()
