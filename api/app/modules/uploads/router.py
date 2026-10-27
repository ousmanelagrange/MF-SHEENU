"""Envoi d'images (publications, stories, albums) : l'image est redimensionnée,
convertie en WebP et rangée dans le dossier de la famille ; l'adresse est renvoyée."""

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from app.core.deps import Ctx
from app.shared import storage

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadOut(BaseModel):
    url: str


@router.post("/image", response_model=UploadOut, status_code=201)
async def upload_image(ctx: Ctx, file: UploadFile = File(...)) -> UploadOut:
    return UploadOut(url=storage.save_photo(ctx.family.id, await file.read()))
