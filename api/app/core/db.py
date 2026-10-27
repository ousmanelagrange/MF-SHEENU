"""Connexion à la base et contexte familial pour la Row Level Security."""

from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_s = get_settings()

# Garde-fous par connexion : une requête SQL qui dépasse 30 s est annulée, et une transaction
# laissée ouverte sans activité plus de 60 s (client disparu, processus tué) est fermée par
# PostgreSQL, ce qui libère ses verrous.
GUARDS = (
    {"options": "-c statement_timeout=30000 -c idle_in_transaction_session_timeout=60000"}
    if _s.db_session_guards
    else {}
)

engine = create_engine(
    _s.sqlalchemy_url,
    pool_pre_ping=True,
    pool_size=_s.db_pool_size,
    max_overflow=_s.db_max_overflow,
    pool_timeout=10,  # sous très forte charge, échouer vite plutôt que bloquer
    connect_args=GUARDS,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Pool séparé pour les tables de la plateforme (journaux, idempotence, compteurs), hors RLS
aux_engine = create_engine(
    _s.sqlalchemy_url,
    pool_pre_ping=True,
    pool_size=_s.db_aux_pool_size,
    max_overflow=5,
    pool_timeout=5,
)
AuxSession = sessionmaker(bind=aux_engine, autoflush=False, expire_on_commit=False)


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
