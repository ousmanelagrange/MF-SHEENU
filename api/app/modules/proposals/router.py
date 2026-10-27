"""Routes des propositions : proposer, lister, accepter, refuser, retirer (RG-13, RG-14)."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import Ctx, FamilyContext
from app.core.errors import bad_request, forbidden, not_found
from app.genealogy.graph import FamilyGraph, load_graph
from app.models import Proposal, ProposalStatus, User
from app.modules.proposals import service
from app.modules.proposals.schemas import ProposalCounts, ProposalCreate, ProposalOut, ReviewIn
from app.shared import audit
from app.shared.notify import notify

router = APIRouter(prefix="/proposals", tags=["proposals"])


def to_out(ctx: FamilyContext, graph: FamilyGraph, p: Proposal, names: dict) -> ProposalOut:
    out = ProposalOut.model_validate(p)
    out.author_name = names.get(p.author_id)
    out.reviewer_name = names.get(p.reviewer_id)
    out.can_review = p.status == ProposalStatus.PENDING and service.can_review(ctx, graph, p)
    return out


def user_names(ctx: FamilyContext, proposals: list[Proposal]) -> dict[UUID, str]:
    ids = {p.author_id for p in proposals} | {p.reviewer_id for p in proposals if p.reviewer_id}
    if not ids:
        return {}
    return {u.id: u.full_name for u in ctx.db.scalars(select(User).where(User.id.in_(ids)))}


def get_proposal(ctx: FamilyContext, proposal_id: UUID) -> Proposal:
    p = ctx.db.get(Proposal, proposal_id)
    if p is None or p.family_id != ctx.family.id:
        raise not_found("Proposition")
    return p


@router.post("", response_model=ProposalOut, status_code=201)
def create_proposal(body: ProposalCreate, ctx: Ctx) -> ProposalOut:
    """Tout membre peut proposer ; les données sont validées dès maintenant."""
    data = service.parse_payload(body.kind, body.payload)
    graph = load_graph(ctx)
    anchor_ids = service.anchors(ctx, body.kind, data)
    for pid in anchor_ids:
        if pid not in graph.persons:
            raise not_found("Personne")
    proposal = Proposal(
        family_id=ctx.family.id,
        author_id=ctx.user.id,
        kind=body.kind,
        payload=data.model_dump(mode="json", exclude_unset=body.kind == "update_person"),
        anchor_ids=[str(pid) for pid in anchor_ids],
        summary=service.describe(ctx, graph, body.kind, data)[:300],
        message=body.message,
    )
    ctx.db.add(proposal)
    ctx.db.flush()
    audit.record(ctx, "propose", "proposal", proposal.id, after={"summary": proposal.summary})
    ctx.db.commit()
    return to_out(ctx, graph, proposal, user_names(ctx, [proposal]))


@router.get("", response_model=list[ProposalOut])
def list_proposals(
    ctx: Ctx,
    view: Literal["review", "mine", "all"] = "review",
    status: Literal["pending", "accepted", "rejected", "withdrawn", "any"] = "pending",
) -> list[ProposalOut]:
    """`review` : celles que je peux valider ; `mine` : les miennes ; `all` : bureau seulement."""
    if view == "all" and not ctx.is_admin:
        raise forbidden("Réservé au bureau.")
    query = select(Proposal).where(Proposal.family_id == ctx.family.id)
    if status != "any":
        query = query.where(Proposal.status == status)
    if view == "mine":
        query = query.where(Proposal.author_id == ctx.user.id)
    proposals = list(ctx.db.scalars(query.order_by(Proposal.created_at.desc()).limit(200)))
    graph = load_graph(ctx)
    if view == "review":
        proposals = [p for p in proposals if service.can_review(ctx, graph, p)]
    names = user_names(ctx, proposals)
    return [to_out(ctx, graph, p, names) for p in proposals]


@router.get("/counts", response_model=ProposalCounts)
def counts(ctx: Ctx) -> ProposalCounts:
    """Compteurs pour le menu : propositions à valider et propositions en attente."""
    pending = list(
        ctx.db.scalars(
            select(Proposal).where(
                Proposal.family_id == ctx.family.id, Proposal.status == ProposalStatus.PENDING
            )
        )
    )
    graph = load_graph(ctx)
    return ProposalCounts(
        to_review=sum(1 for p in pending if service.can_review(ctx, graph, p)),
        mine_pending=sum(1 for p in pending if p.author_id == ctx.user.id),
    )


def close(ctx: FamilyContext, p: Proposal, status: str, note: str | None) -> None:
    p.status = status
    p.reviewer_id = ctx.user.id
    p.review_note = note
    p.reviewed_at = datetime.now(UTC)
    accepted = status == ProposalStatus.ACCEPTED
    notify(
        ctx,
        [p.author_id],
        "proposal_accepted" if accepted else "proposal_rejected",
        f"Proposition {'acceptée' if accepted else 'refusée'} : {p.summary}",
        link="/propositions",
        body=note,
    )


@router.post("/{proposal_id}/accept", response_model=ProposalOut)
def accept(proposal_id: UUID, body: ReviewIn, ctx: Ctx) -> ProposalOut:
    """Applique le changement. S'il n'est plus possible (ex. boucle), l'erreur est renvoyée
    et la proposition reste en attente pour être refusée."""
    p = get_proposal(ctx, proposal_id)
    graph = load_graph(ctx)
    if p.status != ProposalStatus.PENDING:
        raise bad_request("already_reviewed", "Cette proposition a déjà été traitée.")
    if not service.can_review(ctx, graph, p):
        raise forbidden("Vous ne pouvez pas valider cette proposition.")
    data = service.parse_payload(p.kind, p.payload)
    p.result_id = service.apply(ctx, p.kind, data)
    close(ctx, p, ProposalStatus.ACCEPTED, body.note)
    audit.record(ctx, "accept", "proposal", p.id, after={"summary": p.summary})
    ctx.db.commit()
    return to_out(ctx, load_graph(ctx), p, user_names(ctx, [p]))


@router.post("/{proposal_id}/reject", response_model=ProposalOut)
def reject(proposal_id: UUID, body: ReviewIn, ctx: Ctx) -> ProposalOut:
    """Refus avec un motif obligatoire, pour que l'auteur comprenne."""
    p = get_proposal(ctx, proposal_id)
    graph = load_graph(ctx)
    if p.status != ProposalStatus.PENDING:
        raise bad_request("already_reviewed", "Cette proposition a déjà été traitée.")
    if not service.can_review(ctx, graph, p):
        raise forbidden("Vous ne pouvez pas valider cette proposition.")
    if not (body.note and body.note.strip()):
        raise bad_request("note_required", "Indiquez le motif du refus.")
    close(ctx, p, ProposalStatus.REJECTED, body.note.strip())
    audit.record(
        ctx, "reject", "proposal", p.id, after={"summary": p.summary, "note": p.review_note}
    )
    ctx.db.commit()
    return to_out(ctx, graph, p, user_names(ctx, [p]))


@router.post("/{proposal_id}/withdraw", response_model=ProposalOut)
def withdraw(proposal_id: UUID, ctx: Ctx) -> ProposalOut:
    """L'auteur retire sa proposition tant qu'elle n'est pas traitée."""
    p = get_proposal(ctx, proposal_id)
    if p.author_id != ctx.user.id:
        raise forbidden("Seul l'auteur peut retirer sa proposition.")
    if p.status != ProposalStatus.PENDING:
        raise bad_request("already_reviewed", "Cette proposition a déjà été traitée.")
    p.status = ProposalStatus.WITHDRAWN
    p.reviewed_at = datetime.now(UTC)
    audit.record(ctx, "withdraw", "proposal", p.id)
    ctx.db.commit()
    return to_out(ctx, load_graph(ctx), p, user_names(ctx, [p]))
