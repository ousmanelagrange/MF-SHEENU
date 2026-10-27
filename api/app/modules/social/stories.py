"""Routes des stories : photos éphémères visibles 24 heures."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import Ctx
from app.core.errors import forbidden, not_found
from app.genealogy.graph import load_graph
from app.models import Story
from app.modules.social import service
from app.modules.social.schemas import StoryGroup, StoryIn, StoryOut
from app.security.media import own_media

router = APIRouter(prefix="/stories", tags=["social"])

LIFETIME = timedelta(hours=24)


@router.get("", response_model=list[StoryGroup])
def active_stories(ctx: Ctx) -> list[StoryGroup]:
    """Stories encore visibles, regroupées par auteur ; les miennes en premier."""
    stories = list(
        ctx.db.scalars(
            select(Story)
            .where(Story.family_id == ctx.family.id, Story.expires_at > datetime.now(UTC))
            .order_by(Story.created_at)
        )
    )
    people = service.authors(ctx, load_graph(ctx), {s.author_id for s in stories})
    groups: dict[UUID, list[Story]] = {}
    for s in stories:
        groups.setdefault(s.author_id, []).append(s)
    ordered = sorted(
        groups, key=lambda uid: (uid != ctx.user.id, -groups[uid][-1].created_at.timestamp())
    )
    return [
        StoryGroup(
            author=people[uid],
            stories=[StoryOut.model_validate(s, from_attributes=True) for s in groups[uid]],
        )
        for uid in ordered
    ]


@router.post("", response_model=StoryOut, status_code=201)
def add_story(body: StoryIn, ctx: Ctx) -> StoryOut:
    now = datetime.now(UTC)
    story = Story(
        family_id=ctx.family.id,
        author_id=ctx.user.id,
        media_url=own_media(ctx.family.id, body.media_url),
        caption=body.caption,
        created_at=now,
        expires_at=now + LIFETIME,
    )
    ctx.db.add(story)
    ctx.db.commit()
    return StoryOut.model_validate(story, from_attributes=True)


@router.delete("/{story_id}", status_code=204)
def delete_story(story_id: UUID, ctx: Ctx) -> None:
    story = ctx.db.get(Story, story_id)
    if story is None or story.family_id != ctx.family.id:
        raise not_found("Story")
    if story.author_id != ctx.user.id and not service.can_moderate(ctx):
        raise forbidden()
    ctx.db.delete(story)
    ctx.db.commit()
