"""Envoi de messages aux membres.

Deux façons de faire, choisies par MESSAGING_BACKEND :

- « share » (par défaut, gratuit) : rien n'est envoyé par le serveur ; on prépare pour chaque
  destinataire un lien https://wa.me/<numéro>?text=… que le trésorier ou le secrétaire ouvre
  sur son téléphone. WhatsApp s'ouvre avec le message prêt, il n'a plus qu'à l'envoyer.
- « whatsapp_cloud » : envoi direct par l'API WhatsApp Business de Meta. Payante, elle
  demande un compte Business vérifié, un numéro, un jeton (WHATSAPP_TOKEN) et l'identifiant
  du numéro (WHATSAPP_PHONE_ID). Hors de la fenêtre de 24 h après le dernier message du
  destinataire, Meta impose des modèles de message approuvés : à prévoir avant la mise en service.
"""

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

from app.core.config import get_settings


@dataclass
class Delivery:
    status: str  # to_share (lien à ouvrir) | sent | failed | no_phone
    link: str | None = None  # lien wa.me, toujours fourni quand il y a un numéro
    error: str | None = None


def normalize_phone(phone: str | None, default_country: str = "237") -> str | None:
    """Numéro au format international sans « + » ni espaces, comme l'attend WhatsApp.
    Un numéro local à 9 chiffres est supposé camerounais (indicatif 237)."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if phone.strip().startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = default_country + digits
    return digits if 8 <= len(digits) <= 15 else None


def share_link(text: str, phone: str | None = None) -> str:
    """Lien qui ouvre WhatsApp avec le message prêt (vers un numéro, ou au choix du contact)."""
    return f"https://wa.me/{phone or ''}?text={quote(text)}"


class Messenger(Protocol):
    name: str

    def send(self, phone: str | None, text: str) -> Delivery: ...


class ShareMessenger:
    name = "share"

    def send(self, phone: str | None, text: str) -> Delivery:
        number = normalize_phone(phone)
        if not number:
            return Delivery("no_phone")
        return Delivery("to_share", share_link(text, number))


class WhatsAppCloudMessenger:
    name = "whatsapp_cloud"
    API = "https://graph.facebook.com/v20.0/{phone_id}/messages"

    def __init__(self, token: str, phone_id: str):
        self.token = token
        self.phone_id = phone_id

    def send(self, phone: str | None, text: str) -> Delivery:
        number = normalize_phone(phone)
        if not number:
            return Delivery("no_phone")
        link = share_link(text, number)
        payload = {
            "messaging_product": "whatsapp",
            "to": number,
            "type": "text",
            "text": {"body": text},
        }
        request = urllib.request.Request(
            self.API.format(phone_id=self.phone_id),
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            # Adresse fixe en https://graph.facebook.com (pas de schéma choisi par un client)
            with urllib.request.urlopen(request, timeout=10):  # nosec B310
                return Delivery("sent", link)
        except (urllib.error.URLError, TimeoutError) as exc:
            # En cas d'échec, le lien permet encore l'envoi à la main
            return Delivery("failed", link, str(exc)[:200])


def get_messenger() -> Messenger:
    s = get_settings()
    if s.messaging_backend == "whatsapp_cloud" and s.whatsapp_token and s.whatsapp_phone_id:
        return WhatsAppCloudMessenger(s.whatsapp_token, s.whatsapp_phone_id)
    return ShareMessenger()
