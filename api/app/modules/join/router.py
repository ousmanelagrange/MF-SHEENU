"""Rattachement : un lien unique de la famille, posté dans le groupe WhatsApp ; chacun
envoie sa demande ; le bureau ou un chef de branche la place dans l'arbre (RG-04)."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import set_family_context
from app.core.deps import DB, AdminCtx, Ctx, CurrentUser, InviterCtx
from app.core.errors import bad_request, conflict, not_found
from app.core.security import hash_token, new_invitation_token
from app.genealogy.graph import load_graph
from app.models import (
    Family,
    JoinLink,
    JoinRequest,
    JoinStatus,
    Membership,
    Notification,
    Role,
    User,
)
from app.modules.join import service
from app.modules.join.schemas import (
    AcceptIn,
    JoinLinkOut,
    JoinPreview,
    JoinRequestIn,
    JoinRequestOut,
    RejectIn,
)
from app.shared import audit
from app.shared.notify import notify

router = APIRouter(tags=["join"])


# ---------- Lien de la famille ----------


@router.get("/join-link", response_model=JoinLinkOut)
def link_status(ctx: InviterCtx) -> JoinLinkOut:
    link = ctx.db.scalar(select(JoinLink).where(JoinLink.family_id == ctx.family.id))
    return JoinLinkOut(
        active=bool(link and link.active), created_at=link.created_at if link else None
    )


@router.post("/join-link", response_model=JoinLinkOut, status_code=201)
def create_link(ctx: AdminCtx) -> JoinLinkOut:
    """Crée le lien, ou le remplace : l'ancien cesse de fonctionner."""
    token, token_hash = new_invitation_token()
    link = ctx.db.scalar(select(JoinLink).where(JoinLink.family_id == ctx.family.id))
    if link is None:
        link = JoinLink(family_id=ctx.family.id, created_by=ctx.user.id, token_hash=token_hash)
        ctx.db.add(link)
    link.token_hash, link.active, link.created_at = token_hash, True, datetime.now(UTC)
    ctx.db.commit()
    url = f"{get_settings().public_web_url.rstrip('/')}/rattachement/{token}"
    text = (
        f"Vous êtes de la famille « {ctx.family.name} » ? Elle a désormais son espace privé sur "
        f"Sheenu. Ouvrez ce lien, présentez-vous, et le bureau vous rattachera à l'arbre : {url}"
    )
    return JoinLinkOut(active=True, created_at=link.created_at, link=url, share_text=text)


@router.delete("/join-link", status_code=204)
def disable_link(ctx: AdminCtx) -> None:
    link = ctx.db.scalar(select(JoinLink).where(JoinLink.family_id == ctx.family.id))
    if link:
        link.active = False
        ctx.db.commit()


# ---------- Côté visiteur ----------


def _family_from_token(db, token: str) -> Family:  # noqa: ANN001
    link = db.scalar(select(JoinLink).where(JoinLink.token_hash == hash_token(token)))
    if link is None or not link.active:
        raise not_found("Lien de rattachement")
    family = db.get(Family, link.family_id)
    if family.merged_into_id:
        raise not_found("Lien de rattachement")
    return family


@router.get("/join/{token}", response_model=JoinPreview)
def preview(token: str, user: CurrentUser, db: DB) -> JoinPreview:
    """Ce que voit le visiteur : le nom de la famille seulement, rien de l'arbre."""
    family = _family_from_token(db, token)
    member = db.scalar(
        select(Membership).where(Membership.family_id == family.id, Membership.user_id == user.id)
    )
    set_family_context(db, family.id)
    request = db.scalar(
        select(JoinRequest).where(
            JoinRequest.family_id == family.id, JoinRequest.user_id == user.id
        )
    )
    return JoinPreview(
        family_name=family.name,
        community=family.community,
        already_member=member is not None,
        request_status=request.status if request else None,
    )


@router.post("/join/{token}", response_model=JoinPreview, status_code=201)
def ask(token: str, body: JoinRequestIn, user: CurrentUser, db: DB) -> JoinPreview:
    family = _family_from_token(db, token)
    if db.scalar(
        select(Membership).where(Membership.family_id == family.id, Membership.user_id == user.id)
    ):
        raise conflict("already_exists", "Vous êtes déjà membre de cette famille.")
    set_family_context(db, family.id)
    request = db.scalar(
        select(JoinRequest).where(
            JoinRequest.family_id == family.id, JoinRequest.user_id == user.id
        )
    )
    if request and request.status == JoinStatus.PENDING:
        raise conflict("already_exists", "Votre demande est déjà en attente.")
    if request is None:  # une demande refusée peut être renvoyée, complétée
        request = JoinRequest(family_id=family.id, user_id=user.id, lineage="")
        db.add(request)
    for key, value in body.model_dump().items():
        setattr(request, key, value)
    request.status, request.review_note, request.created_at = (
        JoinStatus.PENDING,
        None,
        datetime.now(UTC),
    )
    db.flush()

    # Prévenir ceux qui traitent les demandes (le visiteur n'est pas encore membre : on
    # écrit directement les notifications plutôt que par notify(), qui suppose un membre).
    reviewers = db.scalars(
        select(Membership.user_id).where(
            Membership.family_id == family.id, Membership.role.in_((Role.ADMIN, Role.BRANCH_HEAD))
        )
    )
    name = f"{body.first_name} {body.last_name or ''}".strip()
    db.add_all(
        Notification(
            family_id=family.id,
            user_id=uid,
            kind="join_request",
            title=f"{name} demande à être rattaché(e) à la famille",
            body=body.lineage[:300],
            link="/membres",
        )
        for uid in reviewers
    )
    db.commit()
    return JoinPreview(
        family_name=family.name,
        community=family.community,
        already_member=False,
        request_status=JoinStatus.PENDING,
    )


# ---------- Côté bureau et chefs de branche ----------


def _out(ctx, graph, r: JoinRequest, accounts: dict) -> JoinRequestOut:  # noqa: ANN001
    return JoinRequestOut(
        id=r.id,
        first_name=r.first_name,
        last_name=r.last_name,
        sex=r.sex,
        birth_year=r.birth_year,
        lineage=r.lineage,
        village=r.village,
        country=r.country,
        phone=r.phone,
        account_name=accounts.get(r.user_id, ""),
        status=r.status,
        person=graph.summary(r.person_id) if r.person_id in graph.persons else None,
        review_note=r.review_note,
        created_at=r.created_at,
    )


@router.get("/join-requests", response_model=list[JoinRequestOut])
def list_requests(ctx: Ctx, status: str = JoinStatus.PENDING) -> list[JoinRequestOut]:
    service.require_reviewer(ctx)
    requests = list(
        ctx.db.scalars(
            select(JoinRequest)
            .where(JoinRequest.family_id == ctx.family.id, JoinRequest.status == status)
            .order_by(JoinRequest.created_at)
        )
    )
    accounts = {
        u.id: u.full_name
        for u in ctx.db.scalars(select(User).where(User.id.in_([r.user_id for r in requests])))
    }
    graph = load_graph(ctx)
    return [_out(ctx, graph, r, accounts) for r in requests]


def _pending(ctx, request_id: UUID) -> JoinRequest:  # noqa: ANN001
    service.require_reviewer(ctx)
    r = ctx.db.get(JoinRequest, request_id, with_for_update=True)  # relectures simultanées
    if r is None or r.family_id != ctx.family.id:
        raise not_found("Demande")
    if r.status != JoinStatus.PENDING:
        raise bad_request("already_reviewed", "Cette demande a déjà été traitée.")
    return r


@router.post("/join-requests/{request_id}/accept", response_model=JoinRequestOut)
def accept(request_id: UUID, body: AcceptIn, ctx: Ctx) -> JoinRequestOut:
    r = _pending(ctx, request_id)
    if body.role == "branch_head" and not ctx.is_admin:
        raise bad_request("forbidden_role", "Seul l'administrateur nomme un chef de branche.")
    graph = load_graph(ctx)
    person_id = service.place_person(ctx, graph, r, body.person_id, body.parent_id)
    membership = Membership(
        family_id=ctx.family.id, user_id=r.user_id, person_id=person_id, role=body.role
    )
    ctx.db.add(membership)
    r.status, r.person_id = JoinStatus.ACCEPTED, person_id
    r.reviewed_by, r.reviewed_at = ctx.user.id, datetime.now(UTC)
    ctx.db.flush()
    audit.record(ctx, "join", "membership", membership.id, after={"person_id": str(person_id)})
    notify(
        ctx,
        [r.user_id],
        "join_accepted",
        f"Bienvenue dans la famille « {ctx.family.name} »",
        link=f"/personnes/{person_id}",
        body="Votre demande a été acceptée. Complétez votre fiche et découvrez l'arbre.",
    )
    ctx.db.commit()
    graph = load_graph(ctx)
    return _out(ctx, graph, r, {})


@router.post("/join-requests/{request_id}/reject", response_model=JoinRequestOut)
def reject(request_id: UUID, body: RejectIn, ctx: Ctx) -> JoinRequestOut:
    r = _pending(ctx, request_id)
    r.status, r.review_note = JoinStatus.REJECTED, body.note
    r.reviewed_by, r.reviewed_at = ctx.user.id, datetime.now(UTC)
    ctx.db.commit()
    return _out(ctx, load_graph(ctx), r, {})
