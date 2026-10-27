"""Connexion à la base et contexte familial pour la Row Level Security."""

from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().sqlalchemy_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Session, "after_begin")
def _apply_family_context(session: Session, transaction, connection) -> None:  # noqa: ANN001
    """Positionne app.family_id au début de chaque transaction.

    La RLS PostgreSQL filtre les tables généalogiques sur cette variable : même une
    requête mal écrite ne peut pas lire les données d'une autre famille.
    """
    family_id = session.info.get("family_id")
    connection.execute(
        text("SELECT set_config('app.family_id', :fid, true)"),
        {"fid": str(family_id) if family_id else ""},
    )


def set_family_context(session: Session, family_id) -> None:  # noqa: ANN001
    """Change la famille courante d'une session, y compris dans la transaction ouverte."""
    session.info["family_id"] = family_id
    if session.in_transaction():
        session.execute(
            text("SELECT set_config('app.family_id', :fid, true)"),
            {"fid": str(family_id) if family_id else ""},
        )


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
