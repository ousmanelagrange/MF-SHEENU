"""Envoi de fichiers rangés dans le dossier de la famille ; l'adresse est renvoyée.

- images (publications, stories, albums) : redimensionnées et converties en WebP ;
- audio et vidéo (récits) : conservés tels quels, 30 Mo au plus."""

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from app.core.deps import Ctx
from app.shared import storage

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadOut(BaseModel):
    url: str


class MediaOut(BaseModel):
    url: str
    kind: str  # audio | video


@router.post("/image", response_model=UploadOut, status_code=201)
async def upload_image(ctx: Ctx, file: UploadFile = File(...)) -> UploadOut:
    return UploadOut(url=storage.save_photo(ctx.family.id, await file.read()))


@router.post("/media", response_model=MediaOut, status_code=201)
async def upload_media(ctx: Ctx, file: UploadFile = File(...)) -> MediaOut:
    url, kind = storage.save_media(ctx.family.id, await file.read(), file.content_type)
    return MediaOut(url=url, kind=kind)
