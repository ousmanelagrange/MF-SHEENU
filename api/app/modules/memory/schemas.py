"""Schémas Pydantic du module mémoire (récits, couches de texte, albums, frise)."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.persons.schemas import PersonSummary
from app.modules.social.schemas import Author

LayerName = Literal["original", "fr", "en"]

# ---------- Récits ----------


class NarrativeIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    language: str | None = Field(default=None, max_length=60)
    teller_id: UUID | None = None
    media_url: str | None = Field(default=None, max_length=500)
    media_kind: Literal["audio", "video"] | None = None
    year: int | None = Field(default=None, ge=1000, le=2100)
    era: str | None = Field(default=None, max_length=120)
    place: str | None = Field(default=None, max_length=120)
    person_ids: list[UUID] = []
    # Texte de départ facultatif (transcription ou récit écrit directement)
    transcript: str | None = Field(default=None, max_length=50_000)


class NarrativeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    language: str | None = Field(default=None, max_length=60)
    teller_id: UUID | None = None
    year: int | None = Field(default=None, ge=1000, le=2100)
    era: str | None = Field(default=None, max_length=120)
    place: str | None = Field(default=None, max_length=120)
    person_ids: list[UUID] | None = None


class TextIn(BaseModel):
    layer: LayerName
    text: str = Field(min_length=1, max_length=50_000)


class ReviewIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


class TextOut(BaseModel):
    id: UUID
    layer: str
    text: str
    author: Author
    status: str
    review_note: str | None
    created_at: datetime
    reviewed_at: datetime | None


class LayerState(BaseModel):
    """Ce qu'on affiche d'une couche : la version validée et le nombre de propositions en attente."""

    validated: TextOut | None
    pending: int


class NarrativeCard(BaseModel):
    id: UUID
    title: str
    language: str | None
    teller: PersonSummary | None
    media_kind: str | None
    year: int | None
    era: str | None
    layers: list[str]  # couches validées disponibles
    pending: int  # propositions en attente, toutes couches
    created_at: datetime


class NarrativeOut(NarrativeCard):
    media_url: str | None
    place: str | None
    persons: list[PersonSummary]
    recorded_by: Author
    texts: dict[str, LayerState]
    can_edit: bool
    can_review: bool


# ---------- Albums ----------


class AlbumIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    year: int | None = Field(default=None, ge=1000, le=2100)


class AlbumUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    year: int | None = Field(default=None, ge=1000, le=2100)


class PhotoIn(BaseModel):
    url: str = Field(min_length=5, max_length=500)
    caption: str | None = Field(default=None, max_length=300)
    year: int | None = Field(default=None, ge=1000, le=2100)
    person_ids: list[UUID] = []


class PhotoUpdate(BaseModel):
    caption: str | None = Field(default=None, max_length=300)
    year: int | None = Field(default=None, ge=1000, le=2100)
    person_ids: list[UUID] | None = None


class PhotoOut(BaseModel):
    id: UUID
    album_id: UUID
    url: str
    caption: str | None
    year: int | None
    persons: list[PersonSummary]
    added_by: str
    can_edit: bool


class AlbumCard(BaseModel):
    id: UUID
    title: str
    description: str | None
    year: int | None
    count: int
    cover_url: str | None


class AlbumOut(AlbumCard):
    photos: list[PhotoOut]
    can_edit: bool


# ---------- Frise ----------

TimelineKind = Literal["birth", "death", "union", "narrative", "album", "photo", "life_event"]


class TimelineItem(BaseModel):
    year: int
    day: date | None = None  # date exacte quand elle est connue
    kind: TimelineKind
    title: str
    person: PersonSummary | None = None
    ref_id: UUID | None = None  # récit, album, publication ou personne à ouvrir
