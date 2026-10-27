"""Résumé de la semaine, écrit pour être collé dans le groupe WhatsApp de la famille."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import FamilyContext
from app.genealogy.graph import FamilyGraph
from app.models import ContributionEvent, EventStatus, Narrative, Person, Post, PostKind
from app.modules.contributions import service as contributions
from app.modules.contributions.reports import money
from app.modules.social.memorial import next_occurrence

LIFE_EVENTS = {"birth": "Naissance", "wedding": "Mariage", "death": "Décès", "success": "Réussite"}
MONTHS = (
    "janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split()
)


def day(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}"


def excerpt(text: str, n: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def digest_text(ctx: FamilyContext, graph: FamilyGraph, days: int = 7) -> str:
    """Les nouvelles de la période : arbre, annonces, collectes, récits, anniversaires.
    Les rubriques vides sont omises ; WhatsApp met en gras ce qui est entre *astérisques*."""
    now = datetime.now(UTC)
    since = now - timedelta(days=days)
    db, fid = ctx.db, ctx.family.id
    lines = [
        f"*{ctx.family.name} : les nouvelles de la semaine*",
        f"du {day(since.date())} au {day(now.date())}",
    ]

    newcomers = [
        p
        for p in db.scalars(
            select(Person).where(Person.family_id == fid, Person.created_at >= since)
        )
        if p.id in graph.persons
    ]
    if newcomers:
        # Après un import, des centaines de fiches arrivent d'un coup : on ne cite alors personne
        if len(newcomers) <= 12:
            names = ", ".join(graph.display_name(p.id) for p in newcomers)
            lines += ["", f"*Arbre* : {len(newcomers)} nouvelle(s) personne(s), {names}."]
        else:
            lines += ["", f"*Arbre* : {len(newcomers)} personnes ajoutées."]

    posts = list(
        db.scalars(
            select(Post)
            .where(Post.family_id == fid, Post.created_at >= since, Post.hidden.is_(False))
            .where(Post.kind.in_([PostKind.ANNOUNCEMENT, PostKind.LIFE_EVENT]))
            .order_by(Post.created_at)
        )
    )
    if posts:
        lines += ["", "*Annonces*"]
        for p in posts:
            label = (
                "Bureau"
                if p.kind == PostKind.ANNOUNCEMENT
                else LIFE_EVENTS.get(p.life_event or "", "Événement")
            )
            lines.append(f"- {label} : {excerpt(p.text)}")

    events = list(
        db.scalars(
            select(ContributionEvent).where(
                ContributionEvent.family_id == fid, ContributionEvent.status == EventStatus.OPEN
            )
        )
    )
    if events:
        lines += ["", "*Collectes en cours*"]
        for e in events:
            t = contributions.totals(ctx, e)
            deadline = f", jusqu'au {day(e.deadline)}" if e.deadline else ""
            if t.due:
                share = round(100 * t.collected / t.due)
                progress = (
                    f"{money(t.collected, e.currency)} sur {money(t.due, e.currency)} ({share} %)"
                )
            else:  # collecte libre, sans montant dû
                progress = f"{money(t.collected, e.currency)} collectés"
            lines.append(f"- {e.title} : {progress}{deadline}")

    narratives = list(
        db.scalars(
            select(Narrative).where(Narrative.family_id == fid, Narrative.created_at >= since)
        )
    )
    if narratives:
        titles = ", ".join(f"« {n.title} »" for n in narratives[:4])
        lines += ["", f"*Mémoire* : {len(narratives)} nouveau(x) récit(s), {titles}."]

    today = now.date()
    soon = []
    for pid, p in graph.persons.items():
        if p.is_living and p.birth_date:
            when = next_occurrence(p.birth_date, today)
            if (when - today).days <= 7:
                soon.append(
                    (
                        when,
                        f"{graph.display_name(pid)} ({when.year - p.birth_date.year} ans, le {day(when)})",
                    )
                )
    if soon:
        lines += [
            "",
            "*Anniversaires de la semaine* : " + ", ".join(t for _, t in sorted(soon)) + ".",
        ]

    if len(lines) == 2:
        lines += ["", "Pas de nouvelle cette semaine. Partagez la vôtre sur Sheenu !"]
    lines += ["", f"Tout est sur Sheenu : {get_settings().public_web_url.rstrip('/')}"]
    return "\n".join(lines)
