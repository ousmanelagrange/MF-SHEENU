"""Vues d'ensemble de la famille : résumé de la semaine et carte de la diaspora."""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.deps import Ctx
from app.genealogy.graph import load_graph
from app.integrations.messaging import share_link
from app.modules.overview.diaspora import by_country
from app.modules.overview.digest import digest_text

router = APIRouter(tags=["overview"])


class DigestOut(BaseModel):
    text: str
    share_link: str  # ouvre WhatsApp avec le résumé prêt à envoyer dans le groupe


class CountryCount(BaseModel):
    country: str
    count: int


class DiasporaOut(BaseModel):
    countries: list[CountryCount]
    unknown: int
    living: int


@router.get("/digest", response_model=DigestOut)
def digest(ctx: Ctx, days: int = Query(7, ge=1, le=31)) -> DigestOut:
    text = digest_text(ctx, load_graph(ctx), days)
    return DigestOut(text=text, share_link=share_link(text))


@router.get("/diaspora", response_model=DiasporaOut)
def diaspora(ctx: Ctx) -> DiasporaOut:
    countries, unknown = by_country(load_graph(ctx))
    return DiasporaOut(
        countries=[CountryCount(country=c, count=n) for c, n in countries],
        unknown=unknown,
        living=unknown + sum(n for _, n in countries),
    )
