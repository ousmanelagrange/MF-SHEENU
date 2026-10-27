"""Sorties d'un événement : récapitulatif à coller dans WhatsApp et export pour Excel."""

import csv
import io

from app.genealogy.graph import FamilyGraph
from app.models import ContributionEvent
from app.modules.contributions.schemas import Totals
from app.modules.contributions.service import Row

CURRENCY_LABELS = {"XAF": "FCFA", "XOF": "FCFA", "EUR": "€", "USD": "$", "GBP": "£", "CAD": "$ CA"}
STATUS_LABELS = {"paid": "à jour", "partial": "partiel", "unpaid": "non payé", "exempt": "exempté"}
STATUS_MARKS = {"paid": "✅", "partial": "⏳", "unpaid": "❌", "exempt": "➖"}


def money(amount: int, currency: str) -> str:
    """25000, XAF → « 25 000 FCFA »."""
    return f"{amount:,}".replace(",", " ") + " " + CURRENCY_LABELS.get(currency, currency)


def recap_text(
    event: ContributionEvent,
    totals: Totals,
    rows: list[Row],
    graph: FamilyGraph,
    only_unpaid: bool = False,
) -> str:
    """Message prêt à coller dans le groupe WhatsApp (le gras WhatsApp s'écrit *ainsi*)."""
    lines = [f"*Cotisation : {event.title}*"]
    if event.deadline:
        lines.append(f"Échéance : {event.deadline.strftime('%d/%m/%Y')}")
    target = event.target_amount or totals.due
    progress = f"Collecté : {money(totals.collected, event.currency)}"
    if target:
        progress += (
            f" sur {money(target, event.currency)} ({round(100 * totals.collected / target)} %)"
        )
    lines.append(progress)
    lines.append(f"À jour : {totals.paid}, partiel : {totals.partial}, non payé : {totals.unpaid}")
    lines.append("")

    shown = [r for r in rows if r.person_id in graph.persons and r.status != "exempt"]
    if only_unpaid:
        shown = [r for r in shown if r.status in ("partial", "unpaid")]
        lines.append("*Reste à régler :*")
    shown.sort(key=lambda r: graph.precedence_key(r.person_id))
    for i, r in enumerate(shown, start=1):
        amounts = (
            f"{money(r.paid, event.currency)} / {money(r.amount, event.currency)}"
            if r.amount
            else money(r.paid, event.currency)
        )
        lines.append(f"{i}. {graph.display_name(r.person_id)} : {amounts} {STATUS_MARKS[r.status]}")
    lines.append("")
    lines.append("Détail et paiements sur Sheenu.")
    return "\n".join(lines)


def csv_export(event: ContributionEvent, rows: list[Row], graph: FamilyGraph) -> str:
    """CSV séparé par des points-virgules, avec BOM : Excel l'ouvre correctement en français."""
    out = io.StringIO()
    out.write("\ufeff")  # BOM : Excel reconnaît l'UTF-8 (accents)
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["Personne", "Génération", "Montant dû", "Payé", "Reste", "Statut", "Note"])
    generations = graph.generations()
    rows = sorted(
        (r for r in rows if r.person_id in graph.persons),
        key=lambda r: graph.precedence_key(r.person_id),
    )
    for r in rows:
        writer.writerow(
            [
                graph.display_name(r.person_id),
                generations.get(r.person_id, ""),
                r.amount,
                r.paid,
                max(r.amount - r.paid, 0) if r.status != "exempt" else 0,
                STATUS_LABELS[r.status],
                (r.due.note if r.due else "") or "",
            ]
        )
    return out.getvalue()
