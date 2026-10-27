"""Routes des délégations : confier la fiche d'un ancien à un membre (rôle « délégué »).

Qui peut déléguer : l'administrateur, ou un chef de branche pour une personne de sa branche.
Le délégué peut ensuite modifier cette fiche et sa descendance comme si c'était la sienne.
"""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import Ctx, FamilyContext
from app.core.errors import conflict, forbidden, not_found
from app.genealogy.graph import load_graph
from app.models import Delegation, Membership, Role, User
from app.modules.persons import service as persons_service
from app.shared import audit

router = APIRouter(tags=["delegations"])


class DelegationIn(BaseModel):
    membership_id: UUID


class DelegationOut(BaseModel):
    id: UUID
    person_id: UUID
    membership_id: UUID
    member_name: str


def check_can_delegate(ctx: FamilyContext, person_id: UUID) -> None:
    if ctx.is_admin:
        return
    if ctx.role == Role.BRANCH_HEAD and load_graph(ctx).can_write(ctx.membership, person_id):
        return
    raise forbidden("Seul le bureau ou le chef de branche peut confier cette fiche.")


@router.get("/persons/{person_id}/delegates", response_model=list[DelegationOut])
def list_delegates(person_id: UUID, ctx: Ctx) -> list[DelegationOut]:
    rows = ctx.db.execute(
        select(Delegation, User.full_name)
        .join(Membership, Membership.id == Delegation.membership_id)
        .join(User, User.id == Membership.user_id)
        .where(Delegation.family_id == ctx.family.id, Delegation.person_id == person_id)
    ).all()
    return [
        DelegationOut(id=d.id, person_id=d.person_id, membership_id=d.membership_id, member_name=n)
        for d, n in rows
    ]


@router.post("/persons/{person_id}/delegates", response_model=DelegationOut, status_code=201)
def add_delegate(person_id: UUID, body: DelegationIn, ctx: Ctx) -> DelegationOut:
    persons_service.get_person(ctx, person_id)
    check_can_delegate(ctx, person_id)
    member = ctx.db.get(Membership, body.membership_id)
    if member is None or member.family_id != ctx.family.id:
        raise not_found("Membre")
    exists = ctx.db.scalar(
        select(Delegation).where(
            Delegation.person_id == person_id, Delegation.membership_id == member.id
        )
    )
    if exists:
        raise conflict("already_exists", "Ce membre gère déjà cette fiche.")
    d = Delegation(
        family_id=ctx.family.id,
        person_id=person_id,
        membership_id=member.id,
        created_by=ctx.user.id,
    )
    ctx.db.add(d)
    ctx.db.flush()
    audit.record(ctx, "create", "delegation", d.id, after=audit.snapshot(d))
    ctx.db.commit()
    name = ctx.db.get(User, member.user_id).full_name
    return DelegationOut(id=d.id, person_id=person_id, membership_id=member.id, member_name=name)


@router.delete("/delegations/{delegation_id}", status_code=204)
def remove_delegate(delegation_id: UUID, ctx: Ctx) -> None:
    d = ctx.db.get(Delegation, delegation_id)
    if d is None or d.family_id != ctx.family.id:
        raise not_found("Délégation")
    check_can_delegate(ctx, d.person_id)
    audit.record(ctx, "delete", "delegation", d.id, before=audit.snapshot(d))
    ctx.db.delete(d)
    ctx.db.commit()
