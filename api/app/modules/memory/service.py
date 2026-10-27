"""Règles du module mémoire, sans commit ni contrôle d'accès HTTP.

Qui fait quoi :
- tout membre propose un récit, une transcription ou une traduction, crée un album, ajoute des photos ;
- les gardiens de la mémoire (administrateur, secrétaire, chefs de branche) valident les textes ;
  une proposition d'un gardien est validée d'office ;
- l'auteur d'un récit, d'un album ou d'une photo, ou un gardien, les modifie et les supprime.
"""

from collections import Counter, defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.core.deps import FamilyContext
from app.core.errors import bad_request, not_found
from app.genealogy.graph import FamilyGraph
from app.models import Album, AlbumPhoto, Narrative, NarrativeText, Role, TextStatus
from app.modules.memory.schemas import LayerState, NarrativeCard, NarrativeOut, PhotoOut, TextOut
from app.modules.social.service import authors

CURATOR_ROLES = (Role.ADMIN, Role.SECRETARY, Role.BRANCH_HEAD)


def is_curator(ctx: FamilyContext) -> bool:
    return ctx.role in CURATOR_ROLES


def can_edit(ctx: FamilyContext, owner_id: UUID) -> bool:
    return owner_id == ctx.user.id or is_curator(ctx)


def check_persons(graph: FamilyGraph, ids: list[UUID]) -> list[str]:
    """Vérifie que les personnes citées existent ; renvoie la liste à stocker en JSON."""
    for pid in ids:
        if pid not in graph.persons:
            raise not_found("Personne")
    return [str(p) for p in dict.fromkeys(ids)]


def summaries(graph: FamilyGraph, ids: list) -> list:
    return [graph.summary(UUID(str(p))) for p in ids if UUID(str(p)) in graph.persons]


def get_narrative(ctx: FamilyContext, narrative_id: UUID) -> Narrative:
    n = ctx.db.get(Narrative, narrative_id)
    if n is None or n.family_id != ctx.family.id:
        raise not_found("Récit")
    return n


def get_album(ctx: FamilyContext, album_id: UUID) -> Album:
    a = ctx.db.get(Album, album_id)
    if a is None or a.family_id != ctx.family.id:
        raise not_found("Album")
    return a


# ---------- Couches de texte ----------


def propose_text(ctx: FamilyContext, narrative: Narrative, layer: str, text: str) -> NarrativeText:
    version = NarrativeText(
        family_id=ctx.family.id,
        narrative_id=narrative.id,
        layer=layer,
        text=text.strip(),
        author_id=ctx.user.id,
    )
    ctx.db.add(version)
    ctx.db.flush()
    if is_curator(ctx):
        validate_text(ctx, version)
    return version


def validate_text(ctx: FamilyContext, version: NarrativeText, note: str | None = None) -> None:
    """La version devient la référence de sa couche ; l'ancienne référence est conservée
    comme « remplacée » pour garder l'historique des corrections."""
    if version.status != TextStatus.PENDING:
        raise bad_request("already_reviewed", "Cette version a déjà été relue.")
    # Verrouille le récit : deux validations simultanées de la même couche s'enchaînent
    ctx.db.get(Narrative, version.narrative_id, with_for_update=True)
    previous = ctx.db.scalars(
        select(NarrativeText).where(
            NarrativeText.narrative_id == version.narrative_id,
            NarrativeText.layer == version.layer,
            NarrativeText.status == TextStatus.VALIDATED,
        )
    )
    for old in previous:
        old.status = TextStatus.SUPERSEDED
    version.status = TextStatus.VALIDATED
    version.review_note = note
    version.reviewed_by = ctx.user.id
    version.reviewed_at = datetime.now(UTC)


def reject_text(ctx: FamilyContext, version: NarrativeText, note: str | None) -> None:
    if version.status != TextStatus.PENDING:
        raise bad_request("already_reviewed", "Cette version a déjà été relue.")
    version.status = TextStatus.REJECTED
    version.review_note = note
    version.reviewed_by = ctx.user.id
    version.reviewed_at = datetime.now(UTC)


def texts_out(
    ctx: FamilyContext, graph: FamilyGraph, versions: list[NarrativeText]
) -> list[TextOut]:
    people = authors(ctx, graph, {v.author_id for v in versions})
    return [
        TextOut(
            id=v.id,
            layer=v.layer,
            text=v.text,
            author=people[v.author_id],
            status=v.status,
            review_note=v.review_note,
            created_at=v.created_at,
            reviewed_at=v.reviewed_at,
        )
        for v in versions
    ]


# ---------- Assemblage ----------


def cards(
    ctx: FamilyContext, graph: FamilyGraph, narratives: list[Narrative]
) -> list[NarrativeCard]:
    """Fiches résumées, avec les couches validées et le nombre de propositions en attente."""
    ids = [n.id for n in narratives]
    validated: dict[UUID, set[str]] = defaultdict(set)
    pending: Counter = Counter()
    if ids:
        rows = ctx.db.execute(
            select(NarrativeText.narrative_id, NarrativeText.layer, NarrativeText.status).where(
                NarrativeText.narrative_id.in_(ids),
                NarrativeText.status.in_([TextStatus.VALIDATED, TextStatus.PENDING]),
            )
        )
        for nid, layer, status in rows:
            if status == TextStatus.VALIDATED:
                validated[nid].add(layer)
            else:
                pending[nid] += 1
    order = {"original": 0, "fr": 1, "en": 2}
    return [
        NarrativeCard(
            id=n.id,
            title=n.title,
            language=n.language,
            teller=graph.summary(n.teller_id) if n.teller_id in graph.persons else None,
            media_kind=n.media_kind,
            year=n.year,
            era=n.era,
            layers=sorted(validated[n.id], key=order.get),
            pending=pending[n.id],
            created_at=n.created_at,
        )
        for n in narratives
    ]


def narrative_out(ctx: FamilyContext, graph: FamilyGraph, n: Narrative) -> NarrativeOut:
    versions = list(
        ctx.db.scalars(
            select(NarrativeText).where(
                NarrativeText.narrative_id == n.id,
                NarrativeText.status.in_([TextStatus.VALIDATED, TextStatus.PENDING]),
            )
        )
    )
    validated = {v.layer: v for v in versions if v.status == TextStatus.VALIDATED}
    pending = Counter(v.layer for v in versions if v.status == TextStatus.PENDING)
    shown = texts_out(ctx, graph, list(validated.values()))
    by_layer = {t.layer: t for t in shown}
    card = cards(ctx, graph, [n])[0]
    return NarrativeOut(
        **card.model_dump(),
        media_url=n.media_url,
        place=n.place,
        persons=summaries(graph, n.person_ids),
        recorded_by=authors(ctx, graph, {n.recorded_by})[n.recorded_by],
        texts={
            layer: LayerState(validated=by_layer.get(layer), pending=pending[layer])
            for layer in ("original", "fr", "en")
        },
        can_edit=can_edit(ctx, n.recorded_by),
        can_review=is_curator(ctx),
    )


def photos_out(ctx: FamilyContext, graph: FamilyGraph, photos: list[AlbumPhoto]) -> list[PhotoOut]:
    people = authors(ctx, graph, {p.added_by for p in photos})
    return [
        PhotoOut(
            id=p.id,
            album_id=p.album_id,
            url=p.url,
            caption=p.caption,
            year=p.year,
            persons=summaries(graph, p.person_ids),
            added_by=people[p.added_by].name,
            can_edit=can_edit(ctx, p.added_by),
        )
        for p in photos
    ]
