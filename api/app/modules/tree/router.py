"""Routes de l'arbre : arbre complet, lien de parenté entre deux personnes, statistiques."""

from collections import Counter
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.deps import Ctx
from app.core.errors import not_found
from app.genealogy.graph import load_graph
from app.models import Membership
from app.modules.relations.schemas import ParentChildOut, UnionOut
from app.modules.tree.schemas import KinshipOut, StatsOut, TreeOut

router = APIRouter(tags=["tree"])


@router.get("/tree", response_model=TreeOut)
def tree(ctx: Ctx) -> TreeOut:
    graph = load_graph(ctx)
    ids = sorted(graph.persons, key=graph.precedence_key)
    return TreeOut(
        root_person_id=ctx.family.root_person_id,
        me_person_id=ctx.membership.person_id,
        persons=[graph.summary(pid) for pid in ids],
        parent_child=[
            ParentChildOut.model_validate(link)
            for link in graph.parent_links
            if link.parent_id in graph.persons and link.child_id in graph.persons
        ],
        unions=[
            UnionOut.model_validate(u)
            for u in graph.unions
            if u.person_a_id in graph.persons and u.person_b_id in graph.persons
        ],
    )


@router.get("/kinship", response_model=KinshipOut)
def kinship(
    ctx: Ctx,
    to: UUID,
    from_: UUID | None = Query(default=None, alias="from"),
) -> KinshipOut:
    graph = load_graph(ctx)
    a = from_ or ctx.membership.person_id
    if a is None or a not in graph.persons or to not in graph.persons:
        raise not_found("Personne")
    result = graph.kinship(a, to)
    path = [graph.summary(pid) for pid in result.pop("path")]
    return KinshipOut(**result, path=path)


@router.get("/stats", response_model=StatsOut)
def stats(ctx: Ctx) -> StatsOut:
    graph = load_graph(ctx)
    gens = graph.generations()
    living = sum(1 for p in graph.persons.values() if p.is_living)
    members = ctx.db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.family_id == ctx.family.id, Membership.status == "active")
    )
    by_country = Counter(p.country or "Non renseigné" for p in graph.persons.values())
    by_gen = Counter(g for g in gens.values())
    return StatsOut(
        persons=len(graph.persons),
        living=living,
        deceased=len(graph.persons) - living,
        members=members,
        generations=(max(by_gen) - min(by_gen) + 1) if by_gen else 0,
        by_country=dict(by_country.most_common()),
        by_generation=dict(sorted(by_gen.items())),
    )
