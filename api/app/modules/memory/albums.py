"""Routes des albums photo et de l'identification des personnes sur les photos."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.deps import Ctx
from app.core.errors import forbidden, not_found
from app.genealogy.graph import load_graph
from app.models import Album, AlbumPhoto
from app.modules.memory import service
from app.modules.memory.schemas import (
    AlbumCard,
    AlbumIn,
    AlbumOut,
    AlbumUpdate,
    PhotoIn,
    PhotoOut,
    PhotoUpdate,
)
from app.security.media import own_media

router = APIRouter(tags=["memory"])


def _card(album: Album, count: int, cover: str | None) -> AlbumCard:
    return AlbumCard(
        id=album.id,
        title=album.title,
        description=album.description,
        year=album.year,
        count=count,
        cover_url=cover,
    )


@router.get("/albums", response_model=list[AlbumCard])
def list_albums(ctx: Ctx) -> list[AlbumCard]:
    """Albums de la famille, du plus récent au plus ancien ; la couverture est la première photo."""
    albums = list(
        ctx.db.scalars(
            select(Album)
            .where(Album.family_id == ctx.family.id)
            .order_by(Album.year.desc().nulls_last(), Album.created_at.desc())
        )
    )
    counts = dict(
        ctx.db.execute(
            select(AlbumPhoto.album_id, func.count())
            .where(AlbumPhoto.family_id == ctx.family.id)
            .group_by(AlbumPhoto.album_id)
        ).all()
    )
    covers: dict[UUID, str] = {}
    photos = select(AlbumPhoto).where(AlbumPhoto.family_id == ctx.family.id)
    for p in ctx.db.scalars(photos.order_by(AlbumPhoto.created_at)):
        covers.setdefault(p.album_id, p.url)
    return [_card(a, counts.get(a.id, 0), covers.get(a.id)) for a in albums]


@router.post("/albums", response_model=AlbumCard, status_code=201)
def create_album(body: AlbumIn, ctx: Ctx) -> AlbumCard:
    album = Album(family_id=ctx.family.id, created_by=ctx.user.id, **body.model_dump())
    ctx.db.add(album)
    ctx.db.commit()
    return _card(album, 0, None)


@router.get("/albums/{album_id}", response_model=AlbumOut)
def get_album(album_id: UUID, ctx: Ctx) -> AlbumOut:
    album = service.get_album(ctx, album_id)
    photos = list(
        ctx.db.scalars(
            select(AlbumPhoto)
            .where(AlbumPhoto.album_id == album.id)
            .order_by(AlbumPhoto.created_at)
        )
    )
    out = service.photos_out(ctx, load_graph(ctx), photos)
    return AlbumOut(
        **_card(album, len(out), out[0].url if out else None).model_dump(),
        photos=out,
        can_edit=service.can_edit(ctx, album.created_by),
    )


@router.patch("/albums/{album_id}", response_model=AlbumOut)
def update_album(album_id: UUID, body: AlbumUpdate, ctx: Ctx) -> AlbumOut:
    album = service.get_album(ctx, album_id)
    if not service.can_edit(ctx, album.created_by):
        raise forbidden("Seuls l'auteur et les gardiens de la mémoire modifient un album.")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(album, key, value)
    ctx.db.commit()
    return get_album(album_id, ctx)


@router.delete("/albums/{album_id}", status_code=204)
def delete_album(album_id: UUID, ctx: Ctx) -> None:
    album = service.get_album(ctx, album_id)
    if not service.can_edit(ctx, album.created_by):
        raise forbidden("Seuls l'auteur et les gardiens de la mémoire suppriment un album.")
    ctx.db.delete(album)
    ctx.db.commit()


# ---------- Photos ----------


@router.post("/albums/{album_id}/photos", response_model=PhotoOut, status_code=201)
def add_photo(album_id: UUID, body: PhotoIn, ctx: Ctx) -> PhotoOut:
    """Tout membre enrichit un album ; l'image est envoyée avant via /uploads/image."""
    album = service.get_album(ctx, album_id)
    graph = load_graph(ctx)
    photo = AlbumPhoto(
        family_id=ctx.family.id,
        album_id=album.id,
        url=own_media(ctx.family.id, body.url),
        caption=body.caption,
        year=body.year or album.year,
        person_ids=service.check_persons(graph, body.person_ids),
        added_by=ctx.user.id,
    )
    ctx.db.add(photo)
    ctx.db.commit()
    return service.photos_out(ctx, graph, [photo])[0]


def _photo(ctx, photo_id: UUID) -> AlbumPhoto:  # noqa: ANN001
    photo = ctx.db.get(AlbumPhoto, photo_id)
    if photo is None or photo.family_id != ctx.family.id:
        raise not_found("Photo")
    return photo


@router.patch("/album-photos/{photo_id}", response_model=PhotoOut)
def update_photo(photo_id: UUID, body: PhotoUpdate, ctx: Ctx) -> PhotoOut:
    """Légende, année et personnes reconnues. Identifier quelqu'un est ouvert à tous les
    membres (c'est souvent un cousin qui reconnaît une tante) ; le reste à l'auteur."""
    photo = _photo(ctx, photo_id)
    data = body.model_dump(exclude_unset=True)
    if set(data) - {"person_ids"} and not service.can_edit(ctx, photo.added_by):
        raise forbidden("Seuls l'auteur et les gardiens de la mémoire modifient la légende.")
    graph = load_graph(ctx)
    if "person_ids" in data:
        data["person_ids"] = service.check_persons(graph, data["person_ids"] or [])
    for key, value in data.items():
        setattr(photo, key, value)
    ctx.db.commit()
    return service.photos_out(ctx, graph, [photo])[0]


@router.delete("/album-photos/{photo_id}", status_code=204)
def delete_photo(photo_id: UUID, ctx: Ctx) -> None:
    photo = _photo(ctx, photo_id)
    if not service.can_edit(ctx, photo.added_by):
        raise forbidden("Seuls l'auteur et les gardiens de la mémoire retirent une photo.")
    ctx.db.delete(photo)
    ctx.db.commit()


@router.get("/persons/{person_id}/photos", response_model=list[PhotoOut])
def person_photos(person_id: UUID, ctx: Ctx) -> list[PhotoOut]:
    """Toutes les photos où la personne a été reconnue."""
    photos = list(
        ctx.db.scalars(
            select(AlbumPhoto)
            .where(
                AlbumPhoto.family_id == ctx.family.id,
                AlbumPhoto.person_ids.contains([str(person_id)]),
            )
            .order_by(AlbumPhoto.year.nulls_last(), AlbumPhoto.created_at)
        )
    )
    return service.photos_out(ctx, load_graph(ctx), photos)
