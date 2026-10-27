"""Routes de la réunion de deux familles.

1. POST /family-merges : l'administrateur de la famille d'accueil obtient un code à partager.
2. GET /family-merges/token/{code} : l'administrateur de l'autre famille voit qui l'accueille.
3. POST /family-merges/token/{code}/accept : depuis sa famille (X-Family-Id), il confirme.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import DB, AdminCtx, CurrentUser
from app.core.errors import bad_request, not_found
from app.core.security import hash_token, new_invitation_token
from app.models import Family, FamilyMerge, User
from app.modules.family_merges.service import merge_families
from app.shared import audit

router = APIRouter(prefix="/family-merges", tags=["family-merges"])


class MergeRequestIn(BaseModel):
    days: int = Field(default=7, ge=1, le=30)


class MergeRequestOut(BaseModel):
    token: str
    expires_at: datetime
    share_text: str


class MergePreview(BaseModel):
    target_family_name: str
    requested_by: str
    expires_at: datetime
    valid: bool


class MergeResult(BaseModel):
    target_family_id: str
    persons: int
    links: int
    unions: int
    titles: int
    new_members: int
    merged_accounts: int
    source_root_id: str | None


def aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def load_request(db, token: str) -> FamilyMerge:  # noqa: ANN001
    request = db.scalar(select(FamilyMerge).where(FamilyMerge.token_hash == hash_token(token)))
    if request is None:
        raise not_found("Code de réunion")
    return request


@router.post("", response_model=MergeRequestOut, status_code=201)
def create_request(body: MergeRequestIn, ctx: AdminCtx) -> MergeRequestOut:
    """La famille courante sera la famille d'accueil."""
    token, token_hash = new_invitation_token()
    request = FamilyMerge(
        target_family_id=ctx.family.id,
        token_hash=token_hash,
        requested_by=ctx.user.id,
        expires_at=datetime.now(UTC) + timedelta(days=body.days),
    )
    ctx.db.add(request)
    ctx.db.flush()
    audit.record(ctx, "create", "family_merge", request.id)
    ctx.db.commit()
    link = f"{get_settings().public_web_url.rstrip('/')}/reunir/{token}"
    share = (
        f"{ctx.user.full_name} propose de réunir votre famille à la famille « {ctx.family.name} » "
        f"sur Sheenu. En tant qu'administrateur, ouvrez ce lien pour voir et confirmer : {link}"
    )
    return MergeRequestOut(token=token, expires_at=request.expires_at, share_text=share)


@router.get("/token/{token}", response_model=MergePreview)
def preview(token: str, user: CurrentUser, db: DB) -> MergePreview:
    request = load_request(db, token)
    target = db.get(Family, request.target_family_id)
    requester = db.get(User, request.requested_by)
    valid = (
        request.accepted_at is None
        and aware(request.expires_at) > datetime.now(UTC)
        and target.merged_into_id is None
    )
    return MergePreview(
        target_family_name=target.name,
        requested_by=requester.full_name if requester else "",
        expires_at=request.expires_at,
        valid=valid,
    )


@router.post("/token/{token}/accept", response_model=MergeResult)
def accept(token: str, ctx: AdminCtx) -> MergeResult:
    """La famille courante (X-Family-Id) rejoint la famille d'accueil. Opération définitive."""
    db = ctx.db
    request = load_request(db, token)
    target = db.get(Family, request.target_family_id)
    if request.accepted_at is not None:
        raise bad_request("invalid_code", "Ce code a déjà été utilisé.")
    if aware(request.expires_at) <= datetime.now(UTC):
        raise bad_request("invalid_code", "Ce code a expiré.")
    if target.id == ctx.family.id:
        raise bad_request("same_family", "Une famille ne peut pas être réunie à elle-même.")
    if target.merged_into_id:
        raise bad_request(
            "invalid_code", "La famille d'accueil a elle-même été réunie à une autre."
        )

    source = ctx.family
    summary = merge_families(db, source, target, ctx.user)
    request.source_family_id = source.id
    request.accepted_at = datetime.now(UTC)
    request.accepted_by = ctx.user.id
    request.summary = summary
    # L'audit est écrit dans la famille d'accueil, où l'arbre se trouve désormais.
    ctx.family = target
    audit.record(ctx, "merge_family", "family", target.id, after=summary)
    db.commit()
    return MergeResult(
        target_family_id=str(target.id),
        **{k: summary[k] for k in MergeResult.model_fields if k != "target_family_id"},
    )
