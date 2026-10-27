"""Module social : regroupe les routes du fil, des stories, de la modération et du mémorial."""

from fastapi import APIRouter

from app.modules.social import memorial, moderation, posts, stories

router = APIRouter()
for sub in (posts.router, stories.router, moderation.router, memorial.router):
    router.include_router(sub)
