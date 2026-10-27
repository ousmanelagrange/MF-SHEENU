"""Logique des propositions : validation des données, résumé lisible, droits, application.

Une opération proposée réutilise exactement les services des routes directes
(persons.service, relations.service) : une modification acceptée produit donc le même
résultat, avec les mêmes contrôles, que si le chef de branche l'avait faite lui-même.
"""

from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.core.deps import FamilyContext
from app.core.errors import bad_request
from app.genealogy.graph import FamilyGraph
from app.models import Proposal, Role
from app.modules.persons import service as persons_service
from app.modules.persons.schemas import PersonCreate
from app.modules.proposals.schemas import LinkRef, PersonRef, UnionRef, UpdatePersonPayload
from app.modules.relations import service as relations_service
from app.modules.relations.schemas import ParentChildCreate, UnionCreate

# Schéma attendu pour chaque type d'opération
PAYLOAD_SCHEMAS: dict[str, type[BaseModel]] = {
    "create_person": PersonCreate,
    "update_person": UpdatePersonPayload,
    "archive_person": PersonRef,
    "add_parent_child": ParentChildCreate,
    "add_union": UnionCreate,
    "delete_parent_child": LinkRef,
    "delete_union": UnionRef,
}


def parse_payload(kind: str, payload: dict) -> BaseModel:
    """Valide les données avec le schéma du type d'opération (422 lisible sinon)."""
    try:
        return PAYLOAD_SCHEMAS[kind].model_validate(payload)
    except ValidationError as exc:
        details = "; ".join(e["msg"] for e in exc.errors())
        raise bad_request("validation_error", f"Proposition invalide : {details}") from exc


def anchors(ctx: FamilyContext, kind: str, data: BaseModel) -> list[UUID]:
    """Personnes concernées par l'opération : elles déterminent qui peut la valider."""
    match kind:
        case "create_person":
            return persons_service.anchors_of_new_person(data)
        case "update_person" | "archive_person":
            return [data.person_id]
        case "add_parent_child":
            return [data.parent_id, data.child_id]
        case "add_union":
            return [data.person_a_id, data.person_b_id]
        case "delete_parent_child":
            link = relations_service.get_link(ctx, data.link_id)
            return [link.parent_id, link.child_id]
        case "delete_union":
            union = relations_service.get_union(ctx, data.union_id)
            return [union.person_a_id, union.person_b_id]
    return []


def describe(ctx: FamilyContext, graph: FamilyGraph, kind: str, data: BaseModel) -> str:
    """Phrase lisible par un chef de branche, en français."""

    def name(pid: UUID) -> str:
        return graph.display_name(pid) if pid in graph.persons else "une personne"

    match kind:
        case "create_person":
            new = " ".join(x for x in (data.first_name, data.last_name) if x)
            if data.parent_ids:
                return f"Ajouter {new} comme enfant de {' et '.join(map(name, data.parent_ids))}"
            if data.child_ids:
                return f"Ajouter {new} comme parent de {', '.join(map(name, data.child_ids))}"
            if data.spouse_id:
                return f"Ajouter {new} comme conjoint de {name(data.spouse_id)}"
            return f"Ajouter {new}"
        case "update_person":
            fields = ", ".join(data.changes.model_dump(exclude_unset=True)) or "aucun champ"
            return f"Modifier la fiche de {name(data.person_id)} ({fields})"
        case "archive_person":
            return f"Archiver la fiche de {name(data.person_id)}"
        case "add_parent_child":
            return f"Déclarer {name(data.parent_id)} parent de {name(data.child_id)}"
        case "add_union":
            return f"Unir {name(data.person_a_id)} et {name(data.person_b_id)}"
        case "delete_parent_child":
            link = relations_service.get_link(ctx, data.link_id)
            return (
                f"Retirer le lien entre {name(link.parent_id)} et son enfant {name(link.child_id)}"
            )
        case "delete_union":
            union = relations_service.get_union(ctx, data.union_id)
            return f"Retirer l'union entre {name(union.person_a_id)} et {name(union.person_b_id)}"
    return kind


def can_review(ctx: FamilyContext, graph: FamilyGraph, proposal: Proposal) -> bool:
    """RG-14 : le bureau valide tout ; un chef de branche valide ce qui touche sa branche.

    Un chef de branche ne valide pas ses propres propositions (le bureau le fait).
    """
    if ctx.is_admin:
        return True
    if ctx.role != Role.BRANCH_HEAD or proposal.author_id == ctx.user.id:
        return False
    return any(graph.can_write(ctx.membership, UUID(str(pid))) for pid in proposal.anchor_ids)


def apply(ctx: FamilyContext, kind: str, data: BaseModel) -> UUID | None:
    """Exécute l'opération acceptée ; renvoie l'identifiant de l'élément créé, s'il y en a un."""
    match kind:
        case "create_person":
            return persons_service.create_person(ctx, data).id
        case "update_person":
            return persons_service.update_person(ctx, data.person_id, data.changes).id
        case "archive_person":
            persons_service.archive_person(ctx, data.person_id)
            return data.person_id
        case "add_parent_child":
            return relations_service.add_parent_child(ctx, data).id
        case "add_union":
            return relations_service.add_union(ctx, data).id
        case "delete_parent_child":
            relations_service.delete_parent_child(ctx, data.link_id)
        case "delete_union":
            relations_service.delete_union(ctx, data.union_id)
    return None
