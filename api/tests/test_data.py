"""Phase 2 — données : import GEDCOM, aller-retour export/import, doublons, fusion."""

from app.modules.data.gedcom_import import parse, parse_date
from tests.conftest import Api, build_family

SAMPLE = """0 HEAD
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Ibrahim /Njoya/
1 SEX M
1 BIRT
2 DATE 12 MAR 1920
2 PLAC Foumban
1 DEAT
2 DATE ABT 1990
0 @I2@ INDI
1 NAME Mariama /Pefoura/
1 SEX F
0 @I3@ INDI
1 NAME Issa /Njoya/
1 SEX M
1 NICK Le Sage
1 NOTE Premier fils
2 CONT né à Koutaba
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 MARR
2 DATE 1945
1 CHIL @I3@
0 TRLR
"""


def test_parse_dates():
    assert parse_date("12 MAR 1920")[0].isoformat() == "1920-03-12"
    assert parse_date("ABT 1990") == (None, 1990)
    assert parse_date("inconnue") == (None, None)


def test_parse_sample():
    individuals, families = parse(SAMPLE)
    assert individuals["@I1@"].last_name == "Njoya"
    assert individuals["@I1@"].birth_place == "Foumban"
    assert individuals["@I1@"].is_living is False and individuals["@I1@"].death_year == 1990
    assert individuals["@I3@"].note == "Premier fils\nné à Koutaba"
    assert families[0].partners == ["@I1@", "@I2@"] and families[0].children == ["@I3@"]


def upload(api: Api, text: str):
    return api.c.post(
        "/api/v1/import/gedcom",
        headers=api.h,
        files={"file": ("famille.ged", text.encode(), "text/plain")},
    )


def test_import_gedcom(api):
    r = upload(api, SAMPLE)
    assert r.status_code == 200, r.text
    assert r.json() == {"persons": 3, "unions": 1, "links": 2}
    issa = api.get("/persons", params={"q": "Issa"}).json()["items"][0]
    detail = api.get(f"/persons/{issa['id']}").json()
    assert {p["person"]["first_name"] for p in detail["parents"]} == {"Ibrahim", "Mariama"}
    assert detail["nickname"] == "Le Sage"
    assert upload(api, "pas du gedcom").json()["detail"]["code"] == "invalid_gedcom"


def test_import_requires_admin(client, api):
    member = Api(client, "m@example.com")
    inv = api.post("/invitations", {}).json()
    member.family_id = member.post(f"/invitations/token/{inv['token']}/accept").json()["id"]
    assert upload(member, SAMPLE).status_code == 403


def test_export_then_import_round_trip(client, api):
    build_family(api)
    ged = api.get("/export/gedcom").text
    other = Api(client, "other@example.com")
    other.create_family("Copie")
    r = upload(other, ged).json()
    assert r["persons"] == 12  # 11 personnes de build_family + la fiche de l'administrateur
    assert r["unions"] == 3
    tree = other.get("/tree").json()
    assert len(tree["parent_child"]) == len(api.get("/tree").json()["parent_child"])


def test_duplicates_and_merge(api):
    ids = build_family(api)
    # Doublon de Bachir, saisi à part avec un accent et une photo de village
    dup = api.person("Bâchir", "M", village="Koutaba")
    child_of_dup = api.person("Enfant", "F", parents=[dup])
    pairs = api.get("/duplicates").json()
    assert len(pairs) == 1
    assert {pairs[0]["a"]["id"], pairs[0]["b"]["id"]} == {ids["b1"], dup}

    merged = api.post(f"/persons/{ids['b1']}/merge", {"other_id": dup}).json()
    assert merged["village"] == "Koutaba"  # champ vide complété
    assert {c["person"]["id"] for c in merged["children"]} == {ids["b1c"], child_of_dup}
    assert api.get(f"/persons/{dup}").status_code == 404  # archivée
    assert api.get("/duplicates").json() == []


def test_merge_refuses_ancestor(api):
    ids = build_family(api)
    r = api.post(f"/persons/{ids['a']}/merge", {"other_id": ids["a1"]})
    assert r.json()["detail"]["code"] == "cycle_detected"
