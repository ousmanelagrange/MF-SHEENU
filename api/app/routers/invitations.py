from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import set_family_context
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.core.security import hash_token, new_invitation_token
from app.deps import DB, CurrentUser, FamilyContext, InviterCtx
from app.models import Family, Invitation, Membership, Person, Role, User
from app.routers.families import count_memberships
from app.schemas import (
    InvitationCreate,
    InvitationCreated,
    InvitationOut,
    InvitationPreview,
    MyFamilyOut,
)
from app.services import audit
from app.services.graph import FamilyGraph

router = APIRouter(prefix="/invitations", tags=["invitations"])


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@router.post("", response_model=InvitationCreated, status_code=201)
def create_invitation(body: InvitationCreate, ctx: InviterCtx) -> InvitationCreated:
    db = ctx.db
    if body.role != Role.MEMBER and not ctx.is_admin:
        raise forbidden("Seul un administrateur peut inviter avec un rôle particulier.")
    person_name = None
    if body.person_id:
        p = db.get(Person, body.person_id)
        if p is None or p.family_id != ctx.family.id or p.archived_at:
            raise not_found("Personne")
        graph = FamilyGraph.load(db, ctx.family.id, ctx.family.root_person_id)
        if not graph.can_write(ctx.membership, p.id):
            raise forbidden("Cette personne est hors de votre branche.")
        if db.scalar(
            select(Membership).where(
                Membership.family_id == ctx.family.id, Membership.person_id == p.id
            )
        ):
            raise conflict("already_exists", "Cette personne a déjà un compte dans la famille.")
        person_name = " ".join(x for x in (p.first_name, p.last_name) if x)
    token, token_hash = new_invitation_token()
    inv = Invitation(
        family_id=ctx.family.id,
        token_hash=token_hash,
        person_id=body.person_id,
        role=body.role,
        note=body.note,
        created_by=ctx.user.id,
        expires_at=datetime.now(UTC) + timedelta(days=body.days),
    )
    db.add(inv)
    db.flush()
    audit.record(ctx, "create", "invitation", inv.id, after={"person_id": str(body.person_id)})
    db.commit()
    link = f"{get_settings().public_web_url.rstrip('/')}/join/{token}"
    who = f" {person_name}," if person_name else ""
    share_text = (
        f"Bonjour{who} {ctx.user.full_name} t'invite à rejoindre la famille "
        f"« {ctx.family.name} » sur Sheenu. Ouvre ce lien pour créer ton compte : {link}"
    )
    return InvitationCreated(
        **InvitationOut.model_validate(inv).model_dump(),
        token=token,
        link=link,
        share_text=share_text,
    )


@router.get("", response_model=list[InvitationOut])
def list_invitations(ctx: InviterCtx) -> list[Invitation]:
    q = select(Invitation).where(Invitation.family_id == ctx.family.id)
    if not ctx.is_admin:
        q = q.where(Invitation.created_by == ctx.user.id)
    return list(ctx.db.scalars(q.order_by(Invitation.created_at.desc())))


@router.delete("/{invitation_id}", status_code=204)
def cancel_invitation(invitation_id: UUID, ctx: InviterCtx) -> None:
    inv = ctx.db.get(Invitation, invitation_id)
    if inv is None or inv.family_id != ctx.family.id:
        raise not_found("Invitation")
    if not ctx.is_admin and inv.created_by != ctx.user.id:
        raise forbidden()
    ctx.db.delete(inv)
    audit.record(ctx, "delete", "invitation", invitation_id)
    ctx.db.commit()


def _load_valid(db, token: str) -> Invitation:  # noqa: ANN001
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    if inv is None:
        raise not_found("Invitation")
    return inv


@router.get("/token/{token}", response_model=InvitationPreview)
def preview_invitation(token: str, db: DB) -> InvitationPreview:
    inv = _load_valid(db, token)
    family = db.get(Family, inv.family_id)
    inviter = db.get(User, inv.created_by)
    person_name = None
    if inv.person_id:
        set_family_context(db, inv.family_id)
        p = db.get(Person, inv.person_id)
        if p:
            person_name = " ".join(x for x in (p.first_name, p.last_name) if x)
    valid = inv.used_at is None and _aware(inv.expires_at) > datetime.now(UTC)
    return InvitationPreview(
        family_name=family.name,
        community=family.community,
        invited_by=inviter.full_name if inviter else "",
        person_name=person_name,
        expires_at=inv.expires_at,
        valid=valid,
    )


@router.post("/token/{token}/accept", response_model=MyFamilyOut)
def accept_invitation(token: str, user: CurrentUser, db: DB) -> MyFamilyOut:
    inv = _load_valid(db, token)
    if inv.used_at is not None:
        raise bad_request("invalid_invitation", "Cette invitation a déjà été utilisée.")
    if _aware(inv.expires_at) <= datetime.now(UTC):
        raise bad_request("invalid_invitation", "Cette invitation a expiré.")
    if db.scalar(
        select(Membership).where(
            Membership.family_id == inv.family_id, Membership.user_id == user.id
        )
    ):
        raise conflict("already_exists", "Vous êtes déjà membre de cette famille.")
    if count_memberships(db, user.id) >= get_settings().max_families_per_user:
        raise conflict(
            "family_limit_reached",
            f"Un compte peut appartenir à {get_settings().max_families_per_user} familles au plus.",
        )
    family = db.get(Family, inv.family_id)
    set_family_context(db, family.id)

    person_id = inv.person_id
    if person_id and db.scalar(
        select(Membership).where(
            Membership.family_id == family.id, Membership.person_id == person_id
        )
    ):
        person_id = None
    if person_id is None:
        parts = user.full_name.split(" ", 1)
        person = Person(
            family_id=family.id,
            first_name=parts[0],
            last_name=parts[1] if len(parts) > 1 else None,
            created_by=user.id,
        )
        db.add(person)
        db.flush()
        person_id = person.id

    membership = Membership(
        family_id=family.id, user_id=user.id, person_id=person_id, role=inv.role
    )
    db.add(membership)
    inv.used_at = datetime.now(UTC)
    inv.used_by = user.id
    db.flush()
    ctx = FamilyContext(db=db, user=user, family=family, membership=membership)
    audit.record(ctx, "join", "membership", membership.id, after={"person_id": str(person_id)})
    db.commit()
    return MyFamilyOut(
        id=family.id,
        name=family.name,
        community=family.community,
        description=family.description,
        root_person_id=family.root_person_id,
        created_at=family.created_at,
        role=membership.role,
        person_id=person_id,
    )
