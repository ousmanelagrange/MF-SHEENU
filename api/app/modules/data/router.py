"""Routes des données de l'arbre : export et import GEDCOM, doublons, fusion de fiches."""

from uuid import UUID

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.core.deps import AdminCtx, Ctx
from app.core.errors import bad_request
from app.genealogy.graph import load_graph
from app.modules.data import service
from app.modules.data.gedcom_export import export_gedcom
from app.modules.persons.presenters import person_detail
from app.modules.persons.schemas import PersonDetail, PersonSummary
from app.shared.http import attachment

router = APIRouter(tags=["data"])

MAX_GEDCOM_BYTES = 10 * 1024 * 1024


class ImportResult(BaseModel):
    persons: int
    unions: int
    links: int


class DuplicatePair(BaseModel):
    a: PersonSummary
    b: PersonSummary


class MergeIn(BaseModel):
    other_id: UUID


@router.get("/export/gedcom", response_class=PlainTextResponse)
def gedcom_export(ctx: Ctx) -> PlainTextResponse:
    """Fichier .ged de toute la famille (dates des vivants réservées à l'administrateur)."""
    content = export_gedcom(load_graph(ctx), ctx.family.name, include_living_dates=ctx.is_admin)
    return PlainTextResponse(
        content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": attachment(f"{ctx.family.name}.ged")},
    )


@router.post("/import/gedcom", response_model=ImportResult)
async def gedcom_import(ctx: AdminCtx, file: UploadFile = File(...)) -> ImportResult:
    """Ajoute à l'arbre les personnes d'un fichier GEDCOM (administrateur)."""
    raw = await file.read()
    if len(raw) > MAX_GEDCOM_BYTES:
        raise bad_request("file_too_large", "Fichier trop lourd (10 Mo maximum).")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    result = service.import_gedcom(ctx, text)
    ctx.db.commit()
    return ImportResult(**result)


@router.get("/duplicates", response_model=list[DuplicatePair])
def duplicates(ctx: AdminCtx) -> list[DuplicatePair]:
    """Fiches qui semblent décrire la même personne, à vérifier puis fusionner."""
    graph = load_graph(ctx)
    return [
        DuplicatePair(a=graph.summary(a), b=graph.summary(b))
        for a, b in service.find_duplicates(graph)
    ]


@router.post("/persons/{person_id}/merge", response_model=PersonDetail)
def merge(person_id: UUID, body: MergeIn, ctx: AdminCtx) -> PersonDetail:
    """Fusionne la fiche `other_id` dans `person_id`, qui est conservée."""
    service.merge_persons(ctx, person_id, body.other_id)
    ctx.db.commit()
    return person_detail(ctx, load_graph(ctx), person_id)
