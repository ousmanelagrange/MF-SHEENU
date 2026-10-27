"""Modèles SQLAlchemy, un fichier par domaine. Ce paquet les réexporte tous."""

from app.models.audit import AuditLog
from app.models.family import Family, Membership, Role
from app.models.invitation import Invitation
from app.models.person import Person
from app.models.relation import FamilyUnion, ParentChild
from app.models.title import TitleDefinition, TitleHolding
from app.models.user import User

# Tables isolées par la Row Level Security (une ligne = une famille).
RLS_TABLES = (
    "person",
    "parent_child",
    "family_union",
    "title_definition",
    "title_holding",
    "audit_log",
)

__all__ = [
    "User",
    "Role",
    "Family",
    "Membership",
    "Person",
    "ParentChild",
    "FamilyUnion",
    "TitleDefinition",
    "TitleHolding",
    "Invitation",
    "AuditLog",
    "RLS_TABLES",
]
