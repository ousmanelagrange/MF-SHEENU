"""Routes des familles et de leurs membres (comptes inscrits et rôles)."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.db import set_family_context
from app.core.deps import DB, AdminCtx, Ctx, CurrentUser, FamilyContext
from app.core.errors import bad_request, conflict, not_found
from app.models import Family, Membership, Person, Role, User
from app.modules.families.schemas import (
    FamilyCreate,
    FamilyOut,
    FamilyUpdate,
    MemberOut,
    MemberUpdate,
    MyFamilyOut,
)
from app.shared import audit

router = APIRouter(tags=["families"])


@router.get("/families", response_model=list[MyFamilyOut])
def my_families(user: CurrentUser, db: DB) -> list[MyFamilyOut]:
    rows = db.execute(
        select(Family, Membership)
        .join(Membership, Membership.family_id == Family.id)
        .where(Membership.user_id == user.id, Membership.status == "active")
        .order_by(Family.name)
    ).all()
    return [
        MyFamilyOut(**FamilyOut.model_validate(f).model_dump(), role=m.role, person_id=m.person_id)
        for f, m in rows
    ]


@router.post("/families", response_model=MyFamilyOut, status_code=201)
def create_family(body: FamilyCreate, user: CurrentUser, db: DB) -> MyFamilyOut:
    family = Family(
        name=body.name.strip(),
        community=body.community,
        description=body.description,
        created_by=user.id,
        settings={},
    )
    db.add(family)
    db.flush()
    set_family_context(db, family.id)
    person = Person(
        family_id=family.id,
        first_name=body.my_first_name.strip(),
        last_name=body.my_last_name,
        sex=body.my_sex,
        birth_date=body.my_birth_date,
        created_by=user.id,
    )
    db.add(person)
    db.flush()
    membership = Membership(
        family_id=family.id, user_id=user.id, person_id=person.id, role=Role.ADMIN
    )
    db.add(membership)
    db.flush()
    ctx = FamilyContext(db=db, user=user, family=family, membership=membership)
    audit.record(ctx, "create", "family", family.id, after=audit.snapshot(family))
    audit.record(ctx, "create", "person", person.id, after=audit.snapshot(person))
    db.commit()
    return MyFamilyOut(
        **FamilyOut.model_validate(family).model_dump(), role=Role.ADMIN, person_id=person.id
    )


@router.get("/families/current", response_model=MyFamilyOut)
def current_family(ctx: Ctx) -> MyFamilyOut:
    return MyFamilyOut(
        **FamilyOut.model_validate(ctx.family).model_dump(),
        role=ctx.role,
        person_id=ctx.membership.person_id,
    )


@router.patch("/families/current", response_model=FamilyOut)
def update_family(body: FamilyUpdate, ctx: AdminCtx) -> Family:
    db = ctx.db
    data = body.model_dump(exclude_unset=True)
    if data.get("root_person_id"):
        p = db.get(Person, data["root_person_id"])
        if p is None or p.family_id != ctx.family.id or p.archived_at:
            raise not_found("Personne")
    before = audit.snapshot(ctx.family)
    for key, value in data.items():
        setattr(ctx.family, key, value)
    audit.record(ctx, "update", "family", ctx.family.id, before, audit.snapshot(ctx.family))
    db.commit()
    return ctx.family


def _member_out(m: Membership, u: User) -> MemberOut:
    return MemberOut(
        id=m.id,
        user_id=u.id,
        full_name=u.full_name,
        email=u.email,
        phone=u.phone,
        role=m.role,
        status=m.status,
        person_id=m.person_id,
        branch_person_id=m.branch_person_id,
        joined_at=m.joined_at,
    )


@router.get("/members", response_model=list[MemberOut])
def list_members(ctx: Ctx) -> list[MemberOut]:
    rows = ctx.db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.family_id == ctx.family.id)
        .order_by(User.full_name)
    ).all()
    out = [_member_out(m, u) for m, u in rows]
    if not ctx.is_board:
        # Les coordonnées de compte ne sont visibles que par le bureau.
        for item in out:
            if item.user_id != ctx.user.id:
                item.email = None
                item.phone = None
    return out


@router.patch("/members/{member_id}", response_model=MemberOut)
def update_member(member_id: UUID, body: MemberUpdate, ctx: AdminCtx) -> MemberOut:
    db = ctx.db
    m = db.get(Membership, member_id)
    if m is None or m.family_id != ctx.family.id:
        raise not_found("Membre")
    data = body.model_dump(exclude_unset=True)
    if m.id == ctx.membership.id and data.get("role", Role.ADMIN) != Role.ADMIN:
        admins = db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.family_id == ctx.family.id, Membership.role == Role.ADMIN)
        )
        if admins <= 1:
            raise bad_request("last_admin", "La famille doit garder au moins un administrateur.")
    for key in ("person_id", "branch_person_id"):
        if data.get(key):
            p = db.get(Person, data[key])
            if p is None or p.family_id != ctx.family.id:
                raise not_found("Personne")
    if data.get("person_id"):
        taken = db.scalar(
            select(Membership).where(
                Membership.family_id == ctx.family.id,
                Membership.person_id == data["person_id"],
                Membership.id != m.id,
            )
        )
        if taken:
            raise conflict("already_exists", "Cette fiche est déjà liée à un autre compte.")
    before = audit.snapshot(m)
    for key, value in data.items():
        setattr(m, key, value)
    audit.record(ctx, "update", "membership", m.id, before, audit.snapshot(m))
    db.commit()
    return _member_out(m, db.get(User, m.user_id))
