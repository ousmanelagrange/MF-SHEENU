"""Modèles SQLAlchemy, un fichier par domaine. Ce paquet les réexporte tous."""

from app.models.audit import AuditLog
from app.models.contribution import (
    ContributionDue,
    ContributionEvent,
    ContributionPayment,
    ContributionScale,
    EventStatus,
    PaymentStatus,
)
from app.models.delegation import Delegation
from app.models.family import Family, Membership, Role
from app.models.family_merge import FamilyMerge
from app.models.integration import JoinLink, JoinRequest, JoinStatus, Notification, PaymentIntent
from app.models.invitation import Invitation
from app.models.memory import Album, AlbumPhoto, Layer, Narrative, NarrativeText, TextStatus
from app.models.person import Person
from app.models.platform import (
    AuthSession,
    IdempotencyKey,
    PlatformAudit,
    RequestMetric,
    SecurityEvent,
)
from app.models.proposal import Proposal, ProposalStatus
from app.models.relation import FamilyUnion, ParentChild
from app.models.social import (
    Comment,
    MemorialMessage,
    PollOption,
    PollVote,
    Post,
    PostKind,
    Reaction,
    Report,
    Story,
)
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
    "proposal",
    "delegation",
    "contribution_scale",
    "contribution_event",
    "contribution_due",
    "contribution_payment",
    "post",
    "poll_option",
    "poll_vote",
    "comment",
    "reaction",
    "story",
    "report",
    "memorial_message",
    "narrative",
    "narrative_text",
    "album",
    "album_photo",
    "notification",
    "join_request",
)

__all__ = [
    "User",
    "Role",
    "Family",
    "Membership",
    "FamilyMerge",
    "Person",
    "ParentChild",
    "FamilyUnion",
    "TitleDefinition",
    "TitleHolding",
    "Invitation",
    "AuditLog",
    "Proposal",
    "ProposalStatus",
    "Delegation",
    "ContributionScale",
    "ContributionEvent",
    "ContributionDue",
    "ContributionPayment",
    "EventStatus",
    "PaymentStatus",
    "Post",
    "PostKind",
    "PollOption",
    "PollVote",
    "Comment",
    "Reaction",
    "Story",
    "Report",
    "MemorialMessage",
    "Narrative",
    "NarrativeText",
    "Layer",
    "TextStatus",
    "Album",
    "AlbumPhoto",
    "Notification",
    "JoinLink",
    "JoinRequest",
    "JoinStatus",
    "PaymentIntent",
    "SecurityEvent",
    "AuthSession",
    "IdempotencyKey",
    "RequestMetric",
    "PlatformAudit",
    "RLS_TABLES",
]
