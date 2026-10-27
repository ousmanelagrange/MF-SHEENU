"""Règles communes du module social : droits de modération, auteurs, mise en forme du fil."""

from collections import Counter, defaultdict
from uuid import UUID

from sqlalchemy import func, select

from app.core.deps import FamilyContext
from app.core.errors import not_found
from app.genealogy.graph import FamilyGraph
from app.models import Comment, Membership, PollOption, PollVote, Post, Reaction, Role, User
from app.modules.social.schemas import Author, PollOptionOut, PostOut

MODERATOR_ROLES = (Role.ADMIN, Role.SECRETARY)


def can_moderate(ctx: FamilyContext) -> bool:
    """Le secrétaire et l'administrateur publient les annonces officielles et modèrent."""
    return ctx.role in MODERATOR_ROLES


def get_post(ctx: FamilyContext, post_id: UUID) -> Post:
    post = ctx.db.get(Post, post_id)
    if post is None or post.family_id != ctx.family.id or (post.hidden and not can_moderate(ctx)):
        raise not_found("Publication")
    return post


def authors(ctx: FamilyContext, graph: FamilyGraph, user_ids: set[UUID]) -> dict[UUID, Author]:
    """Nom et fiche de chaque auteur (la fiche donne la photo et le titre)."""
    if not user_ids:
        return {}
    names = {u.id: u.full_name for u in ctx.db.scalars(select(User).where(User.id.in_(user_ids)))}
    persons = {
        m.user_id: m.person_id
        for m in ctx.db.scalars(
            select(Membership).where(
                Membership.family_id == ctx.family.id, Membership.user_id.in_(user_ids)
            )
        )
    }
    out = {}
    for uid in user_ids:
        pid = persons.get(uid)
        person = graph.summary(pid) if pid in graph.persons else None
        out[uid] = Author(
            user_id=uid, name=person.display_name if person else names.get(uid, ""), person=person
        )
    return out


def posts_out(ctx: FamilyContext, graph: FamilyGraph, posts: list[Post]) -> list[PostOut]:
    """Assemble les publications avec réactions, commentaires et sondage, en peu de requêtes."""
    if not posts:
        return []
    ids = [p.id for p in posts]
    reactions: dict[UUID, Counter] = defaultdict(Counter)
    mine: dict[UUID, str] = {}
    for r in ctx.db.scalars(select(Reaction).where(Reaction.post_id.in_(ids))):
        reactions[r.post_id][r.emoji] += 1
        if r.user_id == ctx.user.id:
            mine[r.post_id] = r.emoji
    comments = dict(
        ctx.db.execute(
            select(Comment.post_id, func.count())
            .where(Comment.post_id.in_(ids), Comment.hidden.is_(False))
            .group_by(Comment.post_id)
        ).all()
    )
    options: dict[UUID, list[PollOption]] = defaultdict(list)
    for o in ctx.db.scalars(
        select(PollOption).where(PollOption.post_id.in_(ids)).order_by(PollOption.position)
    ):
        options[o.post_id].append(o)
    votes: Counter = Counter()
    my_votes: dict[UUID, UUID] = {}
    for v in ctx.db.scalars(select(PollVote).where(PollVote.post_id.in_(ids))):
        votes[v.option_id] += 1
        if v.user_id == ctx.user.id:
            my_votes[v.post_id] = v.option_id

    people = authors(ctx, graph, {p.author_id for p in posts})
    moderator = can_moderate(ctx)

    def summary(pid) -> object:  # noqa: ANN001
        pid = UUID(str(pid))
        return graph.summary(pid) if pid in graph.persons else None

    return [
        PostOut(
            id=p.id,
            kind=p.kind,
            life_event=p.life_event,
            text=p.text,
            media=p.media or [],
            persons=[s for s in (summary(pid) for pid in p.person_ids or []) if s],
            author=people[p.author_id],
            on_behalf_of=summary(p.on_behalf_of) if p.on_behalf_of else None,
            pinned=p.pinned,
            hidden=p.hidden,
            created_at=p.created_at,
            edited_at=p.edited_at,
            reactions=dict(reactions[p.id]),
            my_reaction=mine.get(p.id),
            comments_count=comments.get(p.id, 0),
            poll=[PollOptionOut(id=o.id, label=o.label, votes=votes[o.id]) for o in options[p.id]]
            if p.kind == "poll"
            else None,
            my_vote=my_votes.get(p.id),
            can_edit=p.author_id == ctx.user.id,
            can_moderate=moderator,
        )
        for p in posts
    ]
