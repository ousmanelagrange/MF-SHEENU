"""Phase 6 — intégrations : notifications, rattachement, résumé de la semaine, diaspora,
rappels WhatsApp et paiement Mobile Money (simulateur)."""

import json

import pytest

from app.core.config import get_settings
from app.integrations.messaging import normalize_phone
from app.integrations.payments import sign
from tests.conftest import Api, build_family, join_as


def setup(client, api):
    ids = build_family(api)
    ali = join_as(client, api, "ali@example.com", "Ali Test", person_id=ids["a1"])
    return ids, ali


def test_notifications(client, api):
    ids, ali = setup(client, api)
    # Une annonce du bureau prévient toute la famille, sauf son auteur
    api.post("/posts", {"kind": "announcement", "text": "Réunion dimanche"})
    page = ali.get("/notifications").json()
    assert page["unread"] == 1 and page["items"][0]["kind"] == "announcement"
    assert api.get("/notifications").json()["unread"] == 0
    # Un commentaire prévient l'auteur de la publication
    post = ali.post("/posts", {"text": "Photos du mariage"}).json()
    api.post(f"/posts/{post['id']}/comments", {"text": "Magnifique"})
    assert ali.get("/notifications").json()["unread"] == 2
    # Proposition refusée : l'auteur est prévenu avec le motif
    prop = ali.post(
        "/proposals",
        {
            "kind": "create_person",
            "payload": {"first_name": "Nouveau", "sex": "M", "parent_ids": [ids["b"]]},
        },
    )
    assert prop.status_code == 201, prop.text
    api.post(f"/proposals/{prop.json()['id']}/reject", {"note": "À vérifier"})
    rejected = ali.get("/notifications").json()["items"][0]
    assert rejected["kind"] == "proposal_rejected" and rejected["body"] == "À vérifier"
    # Tout marquer comme lu
    assert ali.post("/notifications/read", {}).status_code == 204
    assert ali.get("/notifications").json()["unread"] == 0


def test_join_request_flow(client, api):
    ids = build_family(api)
    link = api.post("/join-link").json()
    token = link["link"].rsplit("/", 1)[1]
    assert "rattachement" in link["link"] and link["share_text"]

    visitor = Api(client, "issa@example.com", "Issa Visiteur")
    preview = visitor.get(f"/join/{token}").json()
    assert preview == {
        "family_name": "Famille Test",
        "community": None,
        "already_member": False,
        "request_status": None,
    }
    # Un visiteur ne voit rien de l'arbre
    assert visitor.get("/persons").status_code in (400, 403)
    r = visitor.post(f"/join/{token}", {"first_name": "Issa", "lineage": "Fils de Bachir"})
    assert r.status_code == 201 and r.json()["request_status"] == "pending"
    assert (
        visitor.post(
            f"/join/{token}", {"first_name": "Issa", "lineage": "Fils de Bachir"}
        ).status_code
        == 409
    )
    # Le bureau est prévenu, puis place la personne comme enfant de Bachir
    assert api.get("/notifications").json()["items"][0]["kind"] == "join_request"
    pending = api.get("/join-requests").json()
    assert pending[0]["account_name"] == "Issa Visiteur"
    accepted = api.post(
        f"/join-requests/{pending[0]['id']}/accept", {"parent_id": ids["b1"]}
    ).json()
    assert accepted["status"] == "accepted" and accepted["person"]["first_name"] == "Issa"
    # Le nouveau membre voit maintenant la famille et son parent
    fam = next(f for f in visitor.get("/families").json() if f["name"] == "Famille Test")
    visitor.family_id = fam["id"]
    me = visitor.get(f"/persons/{accepted['person']['id']}").json()
    assert me["parents"][0]["person"]["first_name"] == "Bachir"
    assert visitor.get("/notifications").json()["items"][0]["kind"] == "join_accepted"
    # Régénérer le lien désactive l'ancien
    api.post("/join-link")
    assert visitor.get(f"/join/{token}").status_code == 404


def test_join_branch_head_scope(client, api):
    ids = build_family(api)
    head = join_as(
        client, api, "chef@example.com", "Chef Beta", person_id=ids["b"], role="branch_head"
    )
    token = api.post("/join-link").json()["link"].rsplit("/", 1)[1]
    visitor = Api(client, "x@example.com", "Xavier Nji")
    visitor.post(f"/join/{token}", {"first_name": "Xavier", "lineage": "Je descends d'Alpha"})
    req = head.get("/join-requests").json()[0]
    # Alpha n'est pas dans la branche de Beta
    assert (
        head.post(f"/join-requests/{req['id']}/accept", {"parent_id": ids["a"]}).status_code == 403
    )
    assert (
        head.post(f"/join-requests/{req['id']}/reject", {"note": "Pas de cette branche"}).json()[
            "status"
        ]
        == "rejected"
    )
    assert visitor.get(f"/join/{token}").json()["request_status"] == "rejected"


def test_digest_and_diaspora(client, api):
    ids, ali = setup(client, api)
    api.patch(f"/persons/{ids['a1']}", {"country": "France"})
    api.patch(f"/persons/{ids['a2']}", {"country": " france "})
    api.patch(f"/persons/{ids['b1']}", {"country": "Cameroun"})
    api.post(
        "/posts", {"kind": "life_event", "life_event": "birth", "text": "Bienvenue à la petite Awa"}
    )
    d = api.get("/digest").json()
    assert d["text"].startswith("*Famille Test : les nouvelles de la semaine*")
    assert "Naissance : Bienvenue à la petite Awa" in d["text"]
    assert d["share_link"].startswith("https://wa.me/?text=")
    dia = api.get("/diaspora").json()
    assert dia["countries"][0] == {"country": "France", "count": 2}
    assert dia["living"] == dia["unknown"] + 3
    assert api.get("/persons", params={"country": "FRANCE"}).json()["total"] == 2


def test_phone_normalization():
    assert normalize_phone("6 77 12 34 56") == "237677123456"
    assert normalize_phone("+33 6 12 34 56 78") == "33612345678"
    assert normalize_phone("0033612345678") == "33612345678"
    assert normalize_phone("12") is None and normalize_phone(None) is None


def _event_with_dues(api, ids):
    event = api.post("/contributions/events", {"title": "Deuil", "kind": "mourning"}).json()
    for pid in (ids["a1"], ids["b1"]):
        api.post(f"/contributions/events/{event['id']}/dues", {"person_id": pid, "amount": 10000})
    return event


def test_reminders_share_links(client, api):
    ids, ali = setup(client, api)
    api.patch(f"/persons/{ids['a1']}", {"phone": "677123456"})
    event = _event_with_dues(api, ids)
    api.post(
        f"/contributions/events/{event['id']}/payments",
        {"person_id": ids["a1"], "amount": 4000, "method": "cash"},
    )
    assert ali.post(f"/contributions/events/{event['id']}/reminders", {}).status_code == 403
    out = api.post(
        f"/contributions/events/{event['id']}/reminders", {"note": "MoMo : 677 00 00 00"}
    ).json()
    assert out["backend"] == "share"
    by_name = {i["person"]["first_name"]: i for i in out["items"]}
    assert by_name["Ali"]["status"] == "to_share"
    assert by_name["Ali"]["link"].startswith("https://wa.me/237677123456?text=")
    assert "Reste : 6 000 FCFA" in by_name["Ali"]["text"]
    assert by_name["Bachir"]["status"] == "no_phone"


@pytest.fixture
def sandbox(monkeypatch):
    monkeypatch.setattr(get_settings(), "payment_backend", "sandbox")
    yield get_settings().payment_webhook_secret


def test_online_payment_disabled_by_default(client, api):
    ids = build_family(api)
    event = _event_with_dues(api, ids)
    assert api.get("/contributions/online").json() == {"enabled": False, "provider": None}
    r = api.post(
        f"/contributions/events/{event['id']}/pay-online",
        {"person_id": ids["a1"], "amount": 1000, "phone": "677000000"},
    )
    assert r.json()["detail"]["code"] == "online_disabled"


def test_online_payment_sandbox(client, api, sandbox):
    ids, ali = setup(client, api)
    event = _event_with_dues(api, ids)
    started = ali.post(
        f"/contributions/events/{event['id']}/pay-online",
        {"person_id": ids["a1"], "amount": 10000, "phone": "677000000"},
    ).json()
    assert started["provider"] == "sandbox" and started["reference"].startswith("SBX-")

    def webhook(status, signature=None):
        body = json.dumps({"reference": started["reference"], "status": status}).encode()
        return client.post(
            "/api/v1/webhooks/payments/sandbox",
            content=body,
            headers={
                "X-Signature": signature or sign(body, sandbox),
                "Content-Type": "application/json",
            },
        )

    assert webhook("success", signature="faux").status_code == 401
    assert webhook("success").status_code == 204
    assert webhook("failed").status_code == 204  # second appel sans effet
    payments = api.get(f"/contributions/events/{event['id']}/payments").json()
    paid = next(p for p in payments if p["id"] == started["payment_id"])
    assert paid["status"] == "validated"
    assert ali.get("/notifications").json()["items"][0]["kind"] == "payment_validated"
