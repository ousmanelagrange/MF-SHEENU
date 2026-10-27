"""Schémas Pydantic du module social."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.persons.schemas import PersonSummary

PostKindName = Literal["post", "announcement", "life_event", "poll"]
LifeEvent = Literal["birth", "wedding", "death", "success", "other"]
Emoji = Literal["like", "love", "pray", "clap"]


class PostIn(BaseModel):
    kind: PostKindName = "post"
    text: str = Field(default="", max_length=5000)
    life_event: LifeEvent | None = None
    media: list[str] = Field(default_factory=list, max_length=10)
    person_ids: list[UUID] = Field(default_factory=list, max_length=30)
    poll_options: list[str] = Field(default_factory=list, max_length=10)
    on_behalf_of: UUID | None = None


class PostUpdate(BaseModel):
    text: str | None = Field(default=None, max_length=5000)
    pinned: bool | None = None  # modération
    hidden: bool | None = None  # modération


class Author(BaseModel):
    user_id: UUID
    name: str
    person: PersonSummary | None = None


class PollOptionOut(BaseModel):
    id: UUID
    label: str
    votes: int


class PostOut(BaseModel):
    id: UUID
    kind: str
    life_event: str | None
    text: str
    media: list[str]
    persons: list[PersonSummary]
    author: Author
    on_behalf_of: PersonSummary | None
    pinned: bool
    hidden: bool
    created_at: datetime
    edited_at: datetime | None
    reactions: dict[str, int]
    my_reaction: str | None
    comments_count: int
    poll: list[PollOptionOut] | None
    my_vote: UUID | None
    can_edit: bool
    can_moderate: bool


class FeedPage(BaseModel):
    items: list[PostOut]
    next_before: datetime | None  # pour charger la suite


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    id: UUID
    author: Author
    text: str
    created_at: datetime
    can_delete: bool


class ReactionIn(BaseModel):
    emoji: Emoji


class VoteIn(BaseModel):
    option_id: UUID


class StoryIn(BaseModel):
    media_url: str = Field(max_length=500)
    caption: str | None = Field(default=None, max_length=300)


class StoryOut(BaseModel):
    id: UUID
    media_url: str
    caption: str | None
    created_at: datetime
    expires_at: datetime


class StoryGroup(BaseModel):
    """Les stories d'un même auteur, de la plus ancienne à la plus récente."""

    author: Author
    stories: list[StoryOut]


class ReportIn(BaseModel):
    post_id: UUID | None = None
    comment_id: UUID | None = None
    reason: str = Field(min_length=2, max_length=300)


class ReportOut(BaseModel):
    id: UUID
    post_id: UUID | None
    comment_id: UUID | None
    excerpt: str
    reason: str
    reporter_name: str
    created_at: datetime


class MemorialIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class MemorialOut(BaseModel):
    id: UUID
    author: Author
    text: str
    created_at: datetime
    can_delete: bool


class Birthday(BaseModel):
    person: PersonSummary
    date: date  # prochaine date anniversaire
    age: int | None  # âge atteint ce jour-là
    in_days: int
