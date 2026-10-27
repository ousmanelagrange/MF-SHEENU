"""Phase 5 — mémoire : récits, couches de transcription et de traduction validées,
albums et identification sur les photos, frise chronologique, envoi d'audio."""

from tests.conftest import build_family, join_as


def setup(client, api):
    ids = build_family(api)
    ali = join_as(client, api, "ali@example.com", "Ali Test", person_id=ids["a1"])
    return ids, ali


def test_narrative_layers_need_validation(client, api):
    ids, ali = setup(client, api)
    # Ali enregistre le récit de la reine racontée par un ancien, avec une transcription
    r = ali.post(
        "/narratives",
        {
            "title": "L'arrivée de la reine à Foumban",
            "language": "Shüpamom",
            "teller_id": ids["a"],
            "year": 1880,
            "person_ids": [ids["root"]],
            "transcript": "Texte en langue bamoun",
        },
    )
    assert r.status_code == 201
    n = r.json()
    assert n["teller"]["first_name"] == "Alpha"
    # Membre simple : la transcription attend la relecture
    assert n["texts"]["original"] == {"validated": None, "pending": 1}
    assert n["can_review"] is False and n["can_edit"] is True

    # Une traduction proposée par Ali, validée par l'administrateur
    fr = ali.post(f"/narratives/{n['id']}/texts", {"layer": "fr", "text": "Traduction v1"}).json()
    assert fr["status"] == "pending"
    assert ali.post(f"/narrative-texts/{fr['id']}/validate", {}).status_code == 403
    assert api.post(f"/narrative-texts/{fr['id']}/validate", {}).json()["status"] == "validated"
    assert api.post(f"/narrative-texts/{fr['id']}/validate", {}).status_code == 400

    # L'administrateur corrige : sa version est validée d'office et remplace la précédente
    v2 = api.post(f"/narratives/{n['id']}/texts", {"layer": "fr", "text": "Traduction v2"}).json()
    assert v2["status"] == "validated"
    detail = ali.get(f"/narratives/{n['id']}").json()
    assert detail["texts"]["fr"]["validated"]["text"] == "Traduction v2"
    history = api.get(f"/narratives/{n['id']}/texts", params={"layer": "fr"}).json()
    assert [h["status"] for h in history] == ["validated", "superseded"]

    # Refus de la transcription avec un motif
    pending = api.get(f"/narratives/{n['id']}/texts", params={"status": "pending"}).json()
    rejected = api.post(f"/narrative-texts/{pending[0]['id']}/reject", {"note": "Inaudible"})
    assert rejected.json()["review_note"] == "Inaudible"

    # Liste, filtres par personne et « à relire »
    cards = api.get("/narratives").json()
    assert cards[0]["layers"] == ["fr"] and cards[0]["pending"] == 0
    assert len(api.get("/narratives", params={"person_id": ids["root"]}).json()) == 1
    assert len(api.get("/narratives", params={"person_id": ids["a"]}).json()) == 1  # conteur
    assert api.get("/narratives", params={"person_id": ids["b"]}).json() == []
    assert api.get("/narratives", params={"to_review": True}).json() == []


def test_narrative_edit_rights(client, api):
    ids, ali = setup(client, api)
    n = api.post("/narratives", {"title": "Le grand marché"}).json()
    assert ali.patch(f"/narratives/{n['id']}", {"title": "Autre"}).status_code == 403
    assert api.patch(f"/narratives/{n['id']}", {"year": 1920}).json()["year"] == 1920
    assert ali.delete(f"/narratives/{n['id']}").status_code == 403
    assert api.delete(f"/narratives/{n['id']}").status_code == 204


def test_albums_and_identification(client, api):
    ids, ali = setup(client, api)
    album = api.post("/albums", {"title": "Mariage de 1975", "year": 1975}).json()
    photo = ali.post(
        f"/albums/{album['id']}/photos",
        {"url": "http://localhost/p1.webp", "caption": "Les mariés", "person_ids": [ids["a"]]},
    ).json()
    assert photo["year"] == 1975  # hérite de l'année de l'album
    assert photo["persons"][0]["first_name"] == "Alpha"
    # Un autre membre reconnaît une personne de plus, sans pouvoir changer la légende
    bachir = join_as(client, api, "bachir@example.com", "Bachir", person_id=ids["b1"])
    tagged = bachir.patch(f"/album-photos/{photo['id']}", {"person_ids": [ids["a"], ids["b"]]})
    assert len(tagged.json()["persons"]) == 2
    assert bachir.patch(f"/album-photos/{photo['id']}", {"caption": "x"}).status_code == 403
    assert len(api.get(f"/persons/{ids['b']}/photos").json()) == 1
    cards = api.get("/albums").json()
    assert cards[0]["count"] == 1 and cards[0]["cover_url"] == "http://localhost/p1.webp"
    assert bachir.delete(f"/album-photos/{photo['id']}").status_code == 403
    assert ali.delete(f"/album-photos/{photo['id']}").status_code == 204


def test_timeline(client, api):
    ids, ali = setup(client, api)
    api.post("/narratives", {"title": "Récit daté", "year": 1890, "person_ids": [ids["root"]]})
    api.post("/albums", {"title": "Album 1975", "year": 1975})
    family = api.get("/timeline").json()
    kinds = {i["kind"] for i in family}
    assert {"birth", "narrative", "album"} <= kinds
    assert family[0]["year"] == 1850  # naissance de la racine, la plus ancienne
    years = [i["year"] for i in family]
    assert years == sorted(years)
    # Autour de la racine : sa naissance, le récit qui la cite, pas l'album
    around = api.get("/timeline", params={"person_id": ids["root"]}).json()
    assert [i["kind"] for i in around] == ["birth", "narrative"]


def test_media_upload(client, api):
    build_family(api)
    files = {"file": ("recit.webm", b"\x1aE\xdf\xa3" + b"0" * 100, "audio/webm;codecs=opus")}
    r = client.post("/api/v1/uploads/media", files=files, headers=api.h)
    assert r.status_code == 201 and r.json()["kind"] == "audio"
    assert r.json()["url"].endswith(".webm")
    bad = {"file": ("x.exe", b"MZ", "application/octet-stream")}
    assert client.post("/api/v1/uploads/media", files=bad, headers=api.h).status_code == 400
