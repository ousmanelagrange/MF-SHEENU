"""Routes des récits et de leurs couches de texte (transcription, traductions FR et EN)."""

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import or_, select

from app.core.deps import Ctx
from app.core.errors import forbidden, not_found
from app.genealogy.graph import load_graph
from app.models import Layer, Narrative, NarrativeText, TextStatus
from app.modules.memory import service
from app.modules.memory.schemas import (
    NarrativeCard,
    NarrativeIn,
    NarrativeOut,
    NarrativeUpdate,
    ReviewIn,
    TextIn,
    TextOut,
)
from app.security.media import own_media
from app.shared import audit
from app.shared.notify import notify

router = APIRouter(tags=["memory"])


@router.get("/narratives", response_model=list[NarrativeCard])
def list_narratives(
    ctx: Ctx,
    person_id: UUID | None = None,
    q: str | None = Query(default=None, max_length=100),
    to_review: bool = False,
) -> list[NarrativeCard]:
    """Récits de la famille, les plus récents d'abord. `person_id` : ceux qui parlent d'une
    personne ou qu'elle a racontés. `to_review` : ceux qui ont des textes à relire."""
    query = select(Narrative).where(Narrative.family_id == ctx.family.id)
    if person_id:
        query = query.where(
            or_(Narrative.teller_id == person_id, Narrative.person_ids.contains([str(person_id)]))
        )
    if q:
        query = query.where(Narrative.title.ilike(f"%{q}%"))
    if to_review:
        pending = select(NarrativeText.narrative_id).where(
            NarrativeText.status == TextStatus.PENDING
        )
        query = query.where(Narrative.id.in_(pending))
    narratives = list(ctx.db.scalars(query.order_by(Narrative.created_at.desc())))
    return service.cards(ctx, load_graph(ctx), narratives)


@router.post("/narratives", response_model=NarrativeOut, status_code=201)
def create_narrative(body: NarrativeIn, ctx: Ctx) -> NarrativeOut:
    graph = load_graph(ctx)
    if body.teller_id and body.teller_id not in graph.persons:
        raise not_found("Conteur")
    n = Narrative(
        family_id=ctx.family.id,
        title=body.title.strip(),
        language=body.language,
        teller_id=body.teller_id,
        recorded_by=ctx.user.id,
        media_url=own_media(ctx.family.id, body.media_url) if body.media_url else None,
        media_kind=body.media_kind if body.media_url else None,
        year=body.year,
        era=body.era,
        place=body.place,
        person_ids=service.check_persons(graph, body.person_ids),
    )
    ctx.db.add(n)
    ctx.db.flush()
    if body.transcript and body.transcript.strip():
        service.propose_text(ctx, n, Layer.ORIGINAL, body.transcript)
    audit.record(ctx, "create", "narrative", n.id, after={"title": n.title})
    ctx.db.commit()
    return service.narrative_out(ctx, graph, n)


@router.get("/narratives/{narrative_id}", response_model=NarrativeOut)
def get_narrative(narrative_id: UUID, ctx: Ctx) -> NarrativeOut:
    return service.narrative_out(ctx, load_graph(ctx), service.get_narrative(ctx, narrative_id))


@router.patch("/narratives/{narrative_id}", response_model=NarrativeOut)
def update_narrative(narrative_id: UUID, body: NarrativeUpdate, ctx: Ctx) -> NarrativeOut:
    n = service.get_narrative(ctx, narrative_id)
    if not service.can_edit(ctx, n.recorded_by):
        raise forbidden("Seuls l'auteur et les gardiens de la mémoire modifient un récit.")
    graph = load_graph(ctx)
    data = body.model_dump(exclude_unset=True)
    if data.get("teller_id") and data["teller_id"] not in graph.persons:
        raise not_found("Conteur")
    if "person_ids" in data:
        data["person_ids"] = service.check_persons(graph, data["person_ids"] or [])
    for key, value in data.items():
        setattr(n, key, value)
    ctx.db.commit()
    return service.narrative_out(ctx, graph, n)


@router.delete("/narratives/{narrative_id}", status_code=204)
def delete_narrative(narrative_id: UUID, ctx: Ctx) -> None:
    n = service.get_narrative(ctx, narrative_id)
    if not service.can_edit(ctx, n.recorded_by):
        raise forbidden("Seuls l'auteur et les gardiens de la mémoire suppriment un récit.")
    audit.record(ctx, "delete", "narrative", n.id, before={"title": n.title})
    ctx.db.delete(n)
    ctx.db.commit()


# ---------- Versions des couches ----------


@router.get("/narratives/{narrative_id}/texts", response_model=list[TextOut])
def list_texts(
    narrative_id: UUID, ctx: Ctx, layer: str | None = None, status: str | None = None
) -> list[TextOut]:
    """Historique des versions : propositions, validées, remplacées, refusées."""
    service.get_narrative(ctx, narrative_id)
    query = select(NarrativeText).where(NarrativeText.narrative_id == narrative_id)
    if layer:
        query = query.where(NarrativeText.layer == layer)
    if status:
        query = query.where(NarrativeText.status == status)
    versions = list(ctx.db.scalars(query.order_by(NarrativeText.created_at.desc())))
    return service.texts_out(ctx, load_graph(ctx), versions)


@router.post("/narratives/{narrative_id}/texts", response_model=TextOut, status_code=201)
def propose_text(narrative_id: UUID, body: TextIn, ctx: Ctx) -> TextOut:
    """Proposer une transcription ou une traduction. Validée d'office si l'auteur est gardien."""
    n = service.get_narrative(ctx, narrative_id)
    version = service.propose_text(ctx, n, body.layer, body.text)
    ctx.db.commit()
    return service.texts_out(ctx, load_graph(ctx), [version])[0]


def _tell_author(ctx, version: NarrativeText, accepted: bool) -> None:  # noqa: ANN001
    narrative = ctx.db.get(Narrative, version.narrative_id)
    notify(
        ctx,
        [version.author_id],
        "text_validated" if accepted else "text_rejected",
        f"Votre texte pour « {narrative.title} » a été {'validé' if accepted else 'refusé'}",
        link=f"/memoire/recits/{narrative.id}",
        body=version.review_note,
    )


def _reviewable(ctx, text_id: UUID) -> NarrativeText:  # noqa: ANN001
    if not service.is_curator(ctx):
        raise forbidden("La relecture est réservée aux gardiens de la mémoire.")
    version = ctx.db.get(NarrativeText, text_id, with_for_update=True)  # relectures simultanées
    if version is None or version.family_id != ctx.family.id:
        raise not_found("Version")
    return version


@router.post("/narrative-texts/{text_id}/validate", response_model=TextOut)
def validate_text(text_id: UUID, body: ReviewIn, ctx: Ctx) -> TextOut:
    version = _reviewable(ctx, text_id)
    service.validate_text(ctx, version, body.note)
    audit.record(ctx, "validate", "narrative_text", version.id, after={"layer": version.layer})
    _tell_author(ctx, version, accepted=True)
    ctx.db.commit()
    return service.texts_out(ctx, load_graph(ctx), [version])[0]


@router.post("/narrative-texts/{text_id}/reject", response_model=TextOut)
def reject_text(text_id: UUID, body: ReviewIn, ctx: Ctx) -> TextOut:
    version = _reviewable(ctx, text_id)
    service.reject_text(ctx, version, body.note)
    _tell_author(ctx, version, accepted=False)
    ctx.db.commit()
    return service.texts_out(ctx, load_graph(ctx), [version])[0]
