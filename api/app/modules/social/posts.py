"""Routes du fil : publications, annonces, sondages, commentaires et réactions."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.deps import Ctx
from app.core.errors import bad_request, forbidden, not_found
from app.genealogy.graph import load_graph
from app.models import Comment, PollOption, PollVote, Post, PostKind, Reaction
from app.modules.social import service
from app.modules.social.schemas import (
    CommentIn,
    CommentOut,
    FeedPage,
    PostIn,
    PostOut,
    PostUpdate,
    ReactionIn,
    VoteIn,
)
from app.security.media import own_media
from app.shared.notify import members, notify

router = APIRouter(tags=["social"])

PAGE_SIZE = 20


@router.get("/feed", response_model=FeedPage)
def feed(
    ctx: Ctx, before: datetime | None = None, kind: str | None = Query(default=None)
) -> FeedPage:
    """Fil de la famille, du plus récent au plus ancien ; les annonces épinglées d'abord
    (première page seulement). `before` charge la page suivante."""
    query = select(Post).where(Post.family_id == ctx.family.id)
    if not service.can_moderate(ctx):
        query = query.where(Post.hidden.is_(False))
    if kind:
        query = query.where(Post.kind == kind)
    pinned: list[Post] = []
    if before is None and not kind:
        pinned = list(
            ctx.db.scalars(query.where(Post.pinned.is_(True)).order_by(Post.created_at.desc()))
        )
        query = query.where(Post.pinned.is_(False))
    if before is not None:
        query = query.where(Post.created_at < before)
    page = list(ctx.db.scalars(query.order_by(Post.created_at.desc()).limit(PAGE_SIZE)))
    items = service.posts_out(ctx, load_graph(ctx), pinned + page)
    return FeedPage(
        items=items, next_before=page[-1].created_at if len(page) == PAGE_SIZE else None
    )


@router.post("/posts", response_model=PostOut, status_code=201)
def create_post(body: PostIn, ctx: Ctx) -> PostOut:
    if body.kind == PostKind.ANNOUNCEMENT and not service.can_moderate(ctx):
        raise forbidden("Seuls le bureau et le secrétaire publient des annonces officielles.")
    if body.kind == PostKind.POLL and len([o for o in body.poll_options if o.strip()]) < 2:
        raise bad_request("validation_error", "Un sondage a besoin d'au moins deux choix.")
    if not body.text.strip() and not body.media:
        raise bad_request("validation_error", "La publication est vide.")
    graph = load_graph(ctx)
    for pid in [*body.person_ids, *([body.on_behalf_of] if body.on_behalf_of else [])]:
        if pid not in graph.persons:
            raise not_found("Personne")
    if body.on_behalf_of and not graph.can_write(ctx.membership, body.on_behalf_of):
        raise forbidden("Vous ne pouvez publier qu'au nom d'une personne qui vous est confiée.")
    post = Post(
        family_id=ctx.family.id,
        author_id=ctx.user.id,
        kind=body.kind,
        life_event=body.life_event if body.kind == PostKind.LIFE_EVENT else None,
        text=body.text.strip(),
        media=[own_media(ctx.family.id, u) for u in body.media],
        person_ids=[str(p) for p in body.person_ids],
        on_behalf_of=body.on_behalf_of,
        pinned=body.kind == PostKind.ANNOUNCEMENT,  # une annonce officielle est épinglée d'office
    )
    ctx.db.add(post)
    ctx.db.flush()
    if body.kind == PostKind.POLL:
        labels = [o.strip() for o in body.poll_options if o.strip()]
        ctx.db.add_all(
            PollOption(family_id=ctx.family.id, post_id=post.id, label=label, position=i)
            for i, label in enumerate(labels)
        )
    if body.kind in (PostKind.ANNOUNCEMENT, PostKind.LIFE_EVENT):
        # Annonces du bureau et annonces de vie (naissance, décès…) : toute la famille est prévenue
        title = (
            "Annonce du bureau" if body.kind == PostKind.ANNOUNCEMENT else "Nouvelle de la famille"
        )
        notify(ctx, members(ctx), body.kind, title, link="/fil", body=post.text[:200])
    ctx.db.commit()
    return service.posts_out(ctx, graph, [post])[0]


@router.get("/posts/{post_id}", response_model=PostOut)
def get_post(post_id: UUID, ctx: Ctx) -> PostOut:
    """Une publication seule (ouverte depuis le mobile ou une notification)."""
    post = service.get_post(ctx, post_id)
    if post.hidden and not service.can_moderate(ctx):
        raise not_found("Publication")
    return service.posts_out(ctx, load_graph(ctx), [post])[0]


@router.patch("/posts/{post_id}", response_model=PostOut)
def update_post(post_id: UUID, body: PostUpdate, ctx: Ctx) -> PostOut:
    """L'auteur corrige son texte ; la modération épingle ou masque."""
    post = service.get_post(ctx, post_id)
    data = body.model_dump(exclude_unset=True)
    if "text" in data:
        if post.author_id != ctx.user.id:
            raise forbidden("Seul l'auteur peut modifier le texte.")
        post.text = data["text"].strip()
        post.edited_at = datetime.now(UTC)
    if ("pinned" in data or "hidden" in data) and not service.can_moderate(ctx):
        raise forbidden("Réservé à la modération.")
    for key in ("pinned", "hidden"):
        if key in data:
            setattr(post, key, data[key])
    ctx.db.commit()
    return service.posts_out(ctx, load_graph(ctx), [post])[0]


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: UUID, ctx: Ctx) -> None:
    post = service.get_post(ctx, post_id)
    if post.author_id != ctx.user.id and not service.can_moderate(ctx):
        raise forbidden("Seuls l'auteur et la modération suppriment une publication.")
    ctx.db.delete(post)
    ctx.db.commit()


# ---------- Réactions et sondages ----------


@router.put("/posts/{post_id}/reaction", status_code=204)
def react(post_id: UUID, body: ReactionIn, ctx: Ctx) -> None:
    """Une réaction par personne : la nouvelle remplace l'ancienne."""
    service.get_post(ctx, post_id)
    # Insertion ou remplacement en une seule instruction : un double appui (deux requêtes au
    # même instant) ne peut pas créer deux réactions ni échouer sur la contrainte d'unicité.
    stmt = insert(Reaction).values(
        id=uuid4(), family_id=ctx.family.id, post_id=post_id, user_id=ctx.user.id, emoji=body.emoji
    )
    ctx.db.execute(
        stmt.on_conflict_do_update(constraint="uq_reaction", set_={"emoji": stmt.excluded.emoji})
    )
    ctx.db.commit()


@router.delete("/posts/{post_id}/reaction", status_code=204)
def unreact(post_id: UUID, ctx: Ctx) -> None:
    existing = ctx.db.scalar(
        select(Reaction).where(Reaction.post_id == post_id, Reaction.user_id == ctx.user.id)
    )
    if existing:
        ctx.db.delete(existing)
        ctx.db.commit()


@router.post("/posts/{post_id}/vote", response_model=PostOut)
def vote(post_id: UUID, body: VoteIn, ctx: Ctx) -> PostOut:
    """Un vote par membre ; voter à nouveau change son choix."""
    post = service.get_post(ctx, post_id)
    option = ctx.db.get(PollOption, body.option_id)
    if option is None or option.post_id != post.id:
        raise not_found("Choix")
    # Même principe que les réactions : un vote par membre, même en cas de double appui
    stmt = insert(PollVote).values(
        id=uuid4(),
        family_id=ctx.family.id,
        post_id=post.id,
        option_id=option.id,
        user_id=ctx.user.id,
    )
    ctx.db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_poll_vote", set_={"option_id": stmt.excluded.option_id}
        )
    )
    ctx.db.commit()
    return service.posts_out(ctx, load_graph(ctx), [post])[0]


# ---------- Commentaires ----------


@router.get("/posts/{post_id}/comments", response_model=list[CommentOut])
def list_comments(post_id: UUID, ctx: Ctx) -> list[CommentOut]:
    service.get_post(ctx, post_id)
    query = select(Comment).where(Comment.post_id == post_id)
    if not service.can_moderate(ctx):
        query = query.where(Comment.hidden.is_(False))
    comments = list(ctx.db.scalars(query.order_by(Comment.created_at)))
    people = service.authors(ctx, load_graph(ctx), {c.author_id for c in comments})
    moderator = service.can_moderate(ctx)
    return [
        CommentOut(
            id=c.id,
            author=people[c.author_id],
            text=c.text,
            created_at=c.created_at,
            can_delete=moderator or c.author_id == ctx.user.id,
        )
        for c in comments
    ]


@router.post("/posts/{post_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(post_id: UUID, body: CommentIn, ctx: Ctx) -> CommentOut:
    post = service.get_post(ctx, post_id)
    comment = Comment(
        family_id=ctx.family.id, post_id=post_id, author_id=ctx.user.id, text=body.text.strip()
    )
    ctx.db.add(comment)
    notify(
        ctx,
        [post.author_id],
        "comment",
        f"{ctx.user.full_name} a commenté votre publication",
        link="/fil",
        body=comment.text[:200],
    )
    ctx.db.commit()
    author = service.authors(ctx, load_graph(ctx), {ctx.user.id})[ctx.user.id]
    return CommentOut(
        id=comment.id,
        author=author,
        text=comment.text,
        created_at=comment.created_at,
        can_delete=True,
    )


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: UUID, ctx: Ctx) -> None:
    comment = ctx.db.get(Comment, comment_id)
    if comment is None or comment.family_id != ctx.family.id:
        raise not_found("Commentaire")
    if comment.author_id != ctx.user.id and not service.can_moderate(ctx):
        raise forbidden("Seuls l'auteur et la modération suppriment un commentaire.")
    ctx.db.delete(comment)
    ctx.db.commit()
