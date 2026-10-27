"""Module mémoire : regroupe les routes des récits, des albums et de la frise."""

from fastapi import APIRouter

from app.modules.memory import albums, narratives, timeline

router = APIRouter()
for sub in (narratives.router, albums.router, timeline.router):
    router.include_router(sub)
