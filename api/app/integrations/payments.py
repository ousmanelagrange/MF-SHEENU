"""Paiement en ligne des cotisations (Mobile Money).

Le déroulé est le même quel que soit le prestataire :

1. le membre demande à payer : `start()` ouvre la transaction chez le prestataire, qui
   envoie une demande de confirmation sur le téléphone du payeur (code PIN MTN / Orange) ;
2. le prestataire prévient Sheenu par un webhook signé : `parse_webhook()` vérifie la
   signature et renvoie la référence et le résultat ;
3. le paiement, créé en « déclaré » à l'étape 1, passe en « validé » ou « refusé ».

Seul le simulateur (« sandbox ») est livré : il permet de tester tout le parcours sans
argent réel. Brancher un vrai prestataire (agrégateur Mobile Money du Cameroun, par exemple)
revient à écrire une classe de plus avec ces deux méthodes, d'après sa documentation, et à
l'ajouter dans `get_gateway()`.
"""

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from typing import Protocol

from app.core.config import get_settings


@dataclass
class Checkout:
    provider_ref: str
    instructions: str  # ce que le payeur doit faire maintenant


@dataclass
class WebhookEvent:
    provider_ref: str
    success: bool


class InvalidSignatureError(Exception):
    pass


class PaymentGateway(Protocol):
    name: str

    def start(self, *, amount: int, phone: str, description: str) -> Checkout: ...

    def parse_webhook(self, body: bytes, signature: str | None) -> WebhookEvent: ...


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class SandboxGateway:
    """Simulateur : aucune somme n'est débitée. Le webhook se déclenche à la main
    (écran de simulation ou test) avec un corps JSON signé en HMAC-SHA256."""

    name = "sandbox"

    def __init__(self, secret: str):
        self.secret = secret

    def start(self, *, amount: int, phone: str, description: str) -> Checkout:
        return Checkout(
            provider_ref=f"SBX-{uuid.uuid4().hex[:12].upper()}",
            instructions=f"Simulation : confirmez le paiement de {amount} FCFA depuis l'écran de test.",
        )

    def parse_webhook(self, body: bytes, signature: str | None) -> WebhookEvent:
        if not signature or not hmac.compare_digest(sign(body, self.secret), signature):
            raise InvalidSignatureError
        data = json.loads(body)
        return WebhookEvent(
            provider_ref=str(data["reference"]), success=data["status"] == "success"
        )


def get_gateway() -> PaymentGateway | None:
    """Le prestataire configuré, ou None si le paiement en ligne est désactivé."""
    s = get_settings()
    if s.payment_backend == "sandbox":
        return SandboxGateway(s.payment_webhook_secret)
    return None
