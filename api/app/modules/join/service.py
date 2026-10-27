"""Règles du rattachement : qui relit, où placer la personne acceptée."""

from uuid import UUID

from sqlalchemy import select

from app.core.deps import FamilyContext
from app.core.errors import conflict, forbidden, not_found
from app.genealogy.graph import FamilyGraph
from app.models import JoinRequest, Membership, ParentChild, Person, Role
from app.shared import audit

REVIEWER_ROLES = (Role.ADMIN, Role.BRANCH_HEAD)


def require_reviewer(ctx: FamilyContext) -> None:
    if ctx.role not in REVIEWER_ROLES:
        raise forbidden("Seuls le bureau et les chefs de branche traitent les rattachements.")


def place_person(
    ctx: FamilyContext,
    graph: FamilyGraph,
    req: JoinRequest,
    person_id: UUID | None,
    parent_id: UUID | None,
) -> UUID:
    """Renvoie la fiche du nouveau membre.

    - `person_id` : la fiche existe déjà (souvent créée par un parent) et n'a pas de compte ;
    - `parent_id` : on crée la fiche et le lien de filiation, déclaré oralement ;
    - ni l'un ni l'autre : fiche créée, à relier plus tard.
    Un chef de branche ne place quelqu'un que dans sa branche."""
    anchor = person_id or parent_id
    if anchor:
        if anchor not in graph.persons:
            raise not_found("Personne")
        if not graph.can_write(ctx.membership, anchor):
            raise forbidden("Cette personne est hors de votre branche.")
    if person_id:
        taken = ctx.db.scalar(
            select(Membership).where(
                Membership.family_id == ctx.family.id, Membership.person_id == person_id
            )
        )
        if taken:
            raise conflict("already_exists", "Cette fiche est déjà reliée à un compte.")
        return person_id

    person = Person(
        family_id=ctx.family.id,
        first_name=req.first_name,
        last_name=req.last_name,
        sex=req.sex,
        birth_year=req.birth_year,
        village=req.village,
        country=req.country,
        phone=req.phone,
        created_by=ctx.user.id,
    )
    ctx.db.add(person)
    ctx.db.flush()
    audit.record(ctx, "create", "person", person.id, after={"from": "join_request"})
    if parent_id:
        link = ParentChild(
            family_id=ctx.family.id,
            parent_id=parent_id,
            child_id=person.id,
            kind="biological",
            certainty="oral",
            source=f"Demande de rattachement : {req.lineage[:200]}",
        )
        ctx.db.add(link)
    return person.id
