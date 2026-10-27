"""Phase 3 — cotisations : barème, montants dus par génération, paiements, clôture, rapports."""

from datetime import date

from tests.conftest import build_family, join_as

# Barème de test : la génération 2 paie 20 000, la 3 paie 10 000, les autres 5 000.
SCALE = {
    "name": "Barème 2026",
    "amounts_by_generation": {"2": 20000, "3": 10000},
    "default_amount": 5000,
    "exempt_under_age": 18,
    "include_spouses": False,
}


def setup(client, api):
    """Famille de test, un trésorier, un membre (Ali), un barème et un événement de deuil."""
    ids = build_family(api)
    # Années de naissance : Adam est mineur, les autres adultes
    year = date.today().year
    for key, born in {
        "a": 1950,
        "b": 1952,
        "a1": 1980,
        "a2": 1982,
        "b1": 1981,
        "a1c": year - 10,
        "b1c": 2000,
    }.items():
        api.patch(f"/persons/{ids[key]}", {"birth_year": born})
    treasurer = join_as(client, api, "tresor@example.com", "Trésorier", role="treasurer")
    ali = join_as(client, api, "ali@example.com", "Ali Test", person_id=ids["a1"])
    scale = api.post("/contributions/scales", SCALE).json()
    event = treasurer.post(
        "/contributions/events",
        {
            "title": "Deuil de Ngougouré",
            "kind": "mourning",
            "scale_id": scale["id"],
            "deadline": "2026-12-15",
        },
    ).json()
    return ids, treasurer, ali, event


def dues_by_name(api, event_id):
    rows = api.get(f"/contributions/events/{event_id}/dues").json()
    return {r["person"]["first_name"]: r for r in rows}


def test_dues_follow_the_scale(client, api):
    ids, treasurer, ali, event = setup(client, api)
    dues = dues_by_name(api, event["id"])
    assert dues["Alpha"]["amount"] == 20000  # génération 2
    assert dues["Ali"]["amount"] == 10000  # génération 3
    assert dues["Basma"]["amount"] == 5000  # génération 4 : montant par défaut
    assert "Adam" not in dues  # mineur exempté
    assert "Awa" not in dues  # conjointe par alliance, exclue par le barème
    assert "Ngougouré" not in dues  # décédée
    t = event["totals"]
    assert t["persons_due"] == len(dues)
    assert t["due"] == sum(r["amount"] for r in dues.values())
    assert t["unpaid"] == len(dues) and t["collected"] == 0


def test_only_treasurer_or_admin_manage(client, api):
    ids, treasurer, ali, event = setup(client, api)
    assert ali.post("/contributions/scales", SCALE).status_code == 403
    assert ali.post("/contributions/events", {"title": "Mariage"}).status_code == 403
    # Mais tout membre voit l'état de chacun (transparence).
    assert ali.get(f"/contributions/events/{event['id']}/dues").status_code == 200


def test_declare_validate_and_statuses(client, api):
    ids, treasurer, ali, event = setup(client, api)
    eid = event["id"]
    # Ali paie 5 000 sur 10 000 par Mobile Money : déclaré, pas encore compté.
    pay = ali.post(
        f"/contributions/events/{eid}/payments",
        {
            "person_id": ids["a1"],
            "amount": 5000,
            "method": "mobile_money",
            "reference": "MP2610.1234",
        },
    ).json()
    assert pay["status"] == "declared"
    assert treasurer.get(f"/contributions/events/{eid}").json()["totals"]["pending"] == 5000
    assert dues_by_name(api, eid)["Ali"]["status"] == "unpaid"
    # Ali ne valide pas lui-même.
    assert ali.post(f"/contributions/payments/{pay['id']}/validate", {}).status_code == 403
    treasurer.post(f"/contributions/payments/{pay['id']}/validate", {})
    assert dues_by_name(api, eid)["Ali"]["status"] == "partial"
    # Le trésorier encaisse en espèces le reste : validé d'office.
    cash = treasurer.post(
        f"/contributions/events/{eid}/payments",
        {"person_id": ids["a1"], "amount": 5000, "method": "cash"},
    ).json()
    assert cash["status"] == "validated"
    assert dues_by_name(api, eid)["Ali"]["status"] == "paid"
    # Ali paie aussi pour sa sœur Amina, depuis la France (montant d'origine en euros).
    for_sister = ali.post(
        f"/contributions/events/{eid}/payments",
        {
            "person_id": ids["a2"],
            "amount": 10000,
            "original_amount": 15,
            "original_currency": "EUR",
        },
    ).json()
    rejected = treasurer.post(f"/contributions/payments/{for_sister['id']}/reject", {})
    assert rejected.json()["detail"]["code"] == "note_required"
    treasurer.post(
        f"/contributions/payments/{for_sister['id']}/reject", {"note": "Transfert non reçu"}
    )
    assert dues_by_name(api, eid)["Amina"]["status"] == "unpaid"
    totals = api.get(f"/contributions/events/{eid}").json()["totals"]
    assert totals["collected"] == 10000 and totals["paid"] == 1


def test_adjust_exempt_and_add(client, api):
    ids, treasurer, ali, event = setup(client, api)
    eid = event["id"]
    dues = dues_by_name(api, eid)
    treasurer.patch(
        f"/contributions/dues/{dues['Basma']['due_id']}", {"exempt": True, "note": "Étudiante"}
    )
    treasurer.patch(f"/contributions/dues/{dues['Beta']['due_id']}", {"amount": 15000})
    dues = dues_by_name(api, eid)
    assert dues["Basma"]["status"] == "exempt" and dues["Basma"]["note"] == "Étudiante"
    assert dues["Beta"]["amount"] == 15000
    # Awa (alliance) ajoutée à la main
    assert (
        treasurer.post(
            f"/contributions/events/{eid}/dues", {"person_id": ids["a_wife1"], "amount": 5000}
        ).status_code
        == 201
    )
    assert (
        treasurer.post(
            f"/contributions/events/{eid}/dues", {"person_id": ids["a_wife1"], "amount": 1}
        ).status_code
        == 409
    )
    assert dues_by_name(api, eid)["Awa"]["amount"] == 5000


def test_close_is_final(client, api):
    ids, treasurer, ali, event = setup(client, api)
    eid = event["id"]
    pay = ali.post(
        f"/contributions/events/{eid}/payments", {"person_id": ids["a1"], "amount": 10000}
    ).json()
    # Pas de clôture tant qu'un paiement attend.
    assert (
        treasurer.post(f"/contributions/events/{eid}/close").json()["detail"]["code"]
        == "payments_pending"
    )
    treasurer.post(f"/contributions/payments/{pay['id']}/validate", {})
    closed = treasurer.post(f"/contributions/events/{eid}/close").json()
    assert closed["status"] == "closed"
    r = ali.post(f"/contributions/events/{eid}/payments", {"person_id": ids["a1"], "amount": 1})
    assert r.json()["detail"]["code"] == "event_closed"
    assert (
        treasurer.patch(f"/contributions/events/{eid}", {"title": "Nouveau titre"}).json()[
            "detail"
        ]["code"]
        == "event_closed"
    )


def test_scale_change_does_not_alter_existing_event(client, api):
    ids, treasurer, ali, event = setup(client, api)
    scale_id = api.get("/contributions/scales").json()[0]["id"]
    api.patch(f"/contributions/scales/{scale_id}", {"amounts_by_generation": {"2": 99999}})
    assert dues_by_name(api, event["id"])["Alpha"]["amount"] == 20000
    new = treasurer.post(
        "/contributions/events", {"title": "Mariage", "kind": "wedding", "scale_id": scale_id}
    ).json()
    assert dues_by_name(api, new["id"])["Alpha"]["amount"] == 99999


def test_free_collection_without_scale(client, api):
    ids, treasurer, ali, event = setup(client, api)
    project = treasurer.post(
        "/contributions/events",
        {"title": "Maison familiale", "kind": "project", "target_amount": 1000000},
    ).json()
    assert project["totals"]["persons_due"] == 0
    ali.post(
        f"/contributions/events/{project['id']}/payments", {"person_id": ids["a1"], "amount": 50000}
    )
    pay = treasurer.get(
        f"/contributions/events/{project['id']}/payments", params={"status": "declared"}
    ).json()[0]
    treasurer.post(
        f"/contributions/payments/{pay['id']}/validate",
        {"amount": 45000, "note": "Frais de transfert déduits"},
    )
    rows = api.get(f"/contributions/events/{project['id']}/dues").json()
    assert rows[0]["paid"] == 45000 and rows[0]["status"] == "paid"


def test_recap_export_and_history(client, api):
    ids, treasurer, ali, event = setup(client, api)
    eid = event["id"]
    treasurer.post(
        f"/contributions/events/{eid}/payments",
        {"person_id": ids["a"], "amount": 20000, "method": "cash"},
    )
    text = ali.get(f"/contributions/events/{eid}/recap").json()["text"]
    assert text.startswith("*Cotisation : Deuil de Ngougouré*")
    assert "Échéance : 15/12/2026" in text
    assert "Alpha : 20 000 FCFA / 20 000 FCFA ✅" in text
    unpaid = ali.get(f"/contributions/events/{eid}/recap", params={"only_unpaid": True}).json()[
        "text"
    ]
    assert "Alpha" not in unpaid and "Reste à régler" in unpaid

    csv = api.get(f"/contributions/events/{eid}/export.csv")
    assert csv.status_code == 200 and "Personne;Génération;Montant dû" in csv.text
    assert "filename*=UTF-8''Deuil%20de%20Ngougour%C3%A9.csv" in csv.headers["content-disposition"]

    history = ali.get(f"/contributions/persons/{ids['a']}").json()
    assert history[0]["event"]["title"] == "Deuil de Ngougouré"
    assert history[0]["status"] == "paid"


def test_member_sees_only_own_declarations(client, api):
    ids, treasurer, ali, event = setup(client, api)
    eid = event["id"]
    other = join_as(client, api, "bachir@example.com", "Bachir", person_id=ids["b1"])
    other.post(
        f"/contributions/events/{eid}/payments",
        {"person_id": ids["b1"], "amount": 10000, "reference": "secret"},
    )
    ali.post(f"/contributions/events/{eid}/payments", {"person_id": ids["a1"], "amount": 10000})
    seen = ali.get(f"/contributions/events/{eid}/payments").json()
    assert [p["person"]["first_name"] for p in seen] == ["Ali"]
    assert len(treasurer.get(f"/contributions/events/{eid}/payments").json()) == 2
