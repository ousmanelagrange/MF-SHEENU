from sqlalchemy import text

from app.core.db import SessionLocal, set_family_context
from tests.conftest import Api, build_family, png_bytes


def test_health(client):
    h = client.get("/health").json()
    assert h["status"] == "ok"
    assert h["rls_enforced"] is True


def test_register_login_refresh(client):
    Api(client, "a@example.com")
    r = client.post(
        "/api/v1/auth/login", json={"login": "A@example.com", "password": "motdepasse123"}
    )
    assert r.status_code == 200
    refresh = r.json()["refresh_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    bad = client.post("/api/v1/auth/login", json={"login": "a@example.com", "password": "faux"})
    assert bad.status_code == 401
    assert bad.json()["detail"]["code"] == "invalid_credentials"


def test_register_with_phone_and_duplicate(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Tel User", "phone": "+237 6 99 00 11 22", "password": "motdepasse123"},
    )
    assert r.status_code == 201
    r = client.post(
        "/api/v1/auth/login", json={"login": "+237699001122", "password": "motdepasse123"}
    )
    assert r.status_code == 200
    dup = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Autre", "phone": "+237699001122", "password": "motdepasse123"},
    )
    assert dup.status_code == 409


def test_logout_all_revokes_tokens(client):
    a = Api(client, "a@example.com")
    assert a.post("/auth/logout-all").status_code == 204
    assert a.get("/auth/me").status_code == 401


def test_family_requires_header_and_membership(client, api):
    other = Api(client, "other@example.com")
    assert other.get("/persons").status_code == 400
    other.family_id = api.family_id
    r = other.get("/persons")
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "not_a_member"


def kin(api, a, b):
    r = api.get("/kinship", params={"from": a, "to": b})
    assert r.status_code == 200, r.text
    return r.json()


def test_tree_generations_and_kinship(api):
    ids = build_family(api)
    tree = api.get("/tree").json()
    gens = {p["id"]: p["generation"] for p in tree["persons"]}
    assert gens[ids["root"]] == 1
    assert gens[ids["husband"]] == 1
    assert gens[ids["a"]] == 2
    assert gens[ids["a_wife2"]] == 2
    assert gens[ids["a1c"]] == 4
    assert len(tree["unions"]) == 3

    assert kin(api, ids["a"], ids["b"])["label"] == "sœur"
    assert kin(api, ids["a1"], ids["a2"])["label"] == "demi-sœur"
    assert kin(api, ids["a1"], ids["b1"])["label"] == "cousin germain"
    assert kin(api, ids["a1c"], ids["b1c"])["label"] == "cousine au 2e degré"
    assert kin(api, ids["a1c"], ids["root"])["label"] == "arrière-grand-mère"
    assert kin(api, ids["b"], ids["a1"])["label"] == "neveu"
    assert kin(api, ids["a1"], ids["b"])["label"] == "tante"
    assert kin(api, ids["a"], ids["a_wife2"])["label"] == "épouse"
    assert kin(api, ids["b"], ids["a_wife1"])["label"] == "épouse de votre frère"
    assert kin(api, ids["a_wife1"], ids["b"])["label"] == "sœur de votre époux"

    k = kin(api, ids["a1c"], ids["b1c"])
    assert k["distance_from"] == 3 and k["distance_to"] == 3
    names = [p["first_name"] for p in k["path"]]
    assert names[0] == "Adam" and names[-1] == "Basma"
    assert len(names) == 7


def test_person_detail(api):
    ids = build_family(api)
    d = api.get(f"/persons/{ids['a']}").json()
    assert {p["person"]["first_name"] for p in d["parents"]} == {"Ngougouré", "Époux"}
    assert [s["person"]["first_name"] for s in d["spouses"]] == ["Awa", "Bintou"]
    assert {c["person"]["first_name"] for c in d["children"]} == {"Ali", "Amina"}
    assert [s["first_name"] for s in d["siblings"]] == ["Beta"]
    assert d["generation"] == 2


def test_cycle_and_parent_limits(api):
    ids = build_family(api)
    r = api.post("/relations/parent-child", {"parent_id": ids["a1c"], "child_id": ids["root"]})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "cycle_detected"
    extra = api.person("Tiers", "M")
    r = api.post("/relations/parent-child", {"parent_id": extra, "child_id": ids["a"]})
    assert r.json()["detail"]["code"] == "too_many_parents"
    r = api.post(
        "/relations/parent-child", {"parent_id": extra, "child_id": ids["a"], "kind": "adoptive"}
    )
    assert r.status_code == 201
    r = api.post("/relations/parent-child", {"parent_id": extra, "child_id": ids["a"]})
    assert r.json()["detail"]["code"] == "already_exists"


def test_raise_root(api):
    ids = build_family(api)
    elder = api.person("Ancêtre", "M", is_living=False)
    r = api.post("/relations/parent-child", {"parent_id": elder, "child_id": ids["root"]})
    assert r.status_code == 201
    api.patch("/families/current", {"root_person_id": elder})
    gens = {p["id"]: p["generation"] for p in api.get("/tree").json()["persons"]}
    assert gens[elder] == 1 and gens[ids["root"]] == 2 and gens[ids["a1c"]] == 5


def test_titles_and_precedence(api):
    ids = build_family(api)
    mfon = api.post("/titles", {"name": "Mfon", "precedence": 1, "badge_color": "#7B1E1E"}).json()
    nji = api.post("/titles", {"name": "Nji", "abbreviation": "Nji", "precedence": 10}).json()
    assert api.post(f"/persons/{ids['b1']}/titles", {"title_id": mfon["id"]}).status_code == 201
    assert (
        api.post(
            f"/persons/{ids['a1']}/titles",
            {"title_id": nji["id"], "conferred_by": "Palais royal de Foumban"},
        ).status_code
        == 201
    )
    items = api.get("/persons", params={"sort": "precedence"}).json()["items"]
    assert items[0]["id"] == ids["b1"]
    assert items[1]["id"] == ids["a1"]
    assert items[1]["display_name"] == "Nji Ali"
    assert items[0]["titles"][0]["name"] == "Mfon"


def test_search_and_pagination(api):
    build_family(api)
    r = api.get("/persons", params={"q": "am", "sort": "name"}).json()
    assert {p["first_name"] for p in r["items"]} == {"Adam", "Amina"}
    page = api.get("/persons", params={"limit": 3, "skip": 0}).json()
    assert len(page["items"]) == 3 and page["total"] == 12


def test_archive_and_audit(api):
    ids = build_family(api)
    assert api.delete(f"/persons/{ids['root']}").json()["detail"]["code"] == "is_root"
    assert api.delete(f"/persons/{api.person_id}").status_code == 403
    assert api.delete(f"/persons/{ids['b1c']}").status_code == 204
    assert api.get(f"/persons/{ids['b1c']}").status_code == 404
    audit = api.get("/audit", params={"entity": "person"}).json()
    assert audit["items"][0]["action"] == "archive"
    assert audit["items"][0]["user_name"] == "Admin Famille"


def test_invitation_flow_and_scope(client, api):
    ids = build_family(api)
    r = api.post("/invitations", {"person_id": ids["a1"]})
    assert r.status_code == 201
    inv = r.json()
    assert inv["link"].endswith(inv["token"])
    assert "Famille Test" in inv["share_text"]

    guest = Api(client, "ali@example.com", "Ali Test")
    preview = client.get(f"/api/v1/invitations/token/{inv['token']}").json()
    assert preview["valid"] and preview["person_name"] == "Ali"
    r = guest.post(f"/invitations/token/{inv['token']}/accept")
    assert r.status_code == 200
    guest.family_id = r.json()["id"]
    assert r.json()["person_id"] == ids["a1"]
    # usage unique
    other = Api(client, "x@example.com")
    assert other.post(f"/invitations/token/{inv['token']}/accept").status_code == 400

    # Périmètre : Ali modifie sa fiche et ajoute un enfant, mais pas la fiche de sa tante.
    assert guest.patch(f"/persons/{ids['a1']}", {"village": "Foumban"}).status_code == 200
    assert guest.patch(f"/persons/{ids['b']}", {"village": "X"}).json()["detail"]["code"] == (
        "out_of_scope"
    )
    child = guest.person("Bébé", "F", parents=[ids["a1"]])
    assert guest.get(f"/persons/{child}").json()["can_edit"] is True
    assert guest.get(f"/persons/{ids['b']}").json()["can_edit"] is False
    r = guest.post("/persons", {"first_name": "Intrus", "parent_ids": [ids["b"]]})
    assert r.json()["detail"]["code"] == "out_of_scope"
    # Un membre n'invite pas et ne voit pas l'audit.
    assert guest.post("/invitations", {}).status_code == 403
    assert guest.get("/audit").status_code == 403


def test_branch_head_scope(client, api):
    ids = build_family(api)
    inv = api.post("/invitations", {"role": "branch_head"}).json()
    head = Api(client, "head@example.com", "Chef Branche")
    head.family_id = head.post(f"/invitations/token/{inv['token']}/accept").json()["id"]
    members = api.get("/members").json()
    m = next(x for x in members if x["full_name"] == "Chef Branche")
    api.patch(f"/members/{m['id']}", {"branch_person_id": ids["b"]})
    assert head.patch(f"/persons/{ids['b1c']}", {"village": "Koutaba"}).status_code == 200
    assert head.patch(f"/persons/{ids['a1']}", {"village": "X"}).status_code == 403
    assert head.post("/invitations", {"person_id": ids["b1"]}).status_code == 201
    assert head.post("/invitations", {"person_id": ids["a1"]}).status_code == 403


def test_family_limit(client):
    a = Api(client, "multi@example.com")
    a.create_family("F1")
    a.create_family("F2")
    r = a.post("/families", {"name": "F3", "my_first_name": "Moi"})
    assert r.json()["detail"]["code"] == "family_limit_reached"
    assert len(a.get("/families").json()) == 2


def test_contact_visibility(client, api):
    ids = build_family(api)
    api.patch(f"/persons/{ids['b']}", {"phone": "+237600000000", "contact_visibility": "board"})
    inv = api.post("/invitations", {"person_id": ids["a1"]}).json()
    guest = Api(client, "ali@example.com", "Ali Test")
    guest.family_id = guest.post(f"/invitations/token/{inv['token']}/accept").json()["id"]
    assert guest.get(f"/persons/{ids['b']}").json()["phone"] is None
    assert api.get(f"/persons/{ids['b']}").json()["phone"] == "+237600000000"


def test_rls_isolation_between_families(client, api):
    build_family(api)
    other = Api(client, "other@example.com")
    other.create_family("Autre famille")
    other.person("Secret", "M")
    # Via l'API : chacun ne voit que sa famille.
    names = {p["first_name"] for p in api.get("/tree").json()["persons"]}
    assert "Secret" not in names
    # Directement en SQL : la RLS filtre même une requête sans clause WHERE.
    with SessionLocal() as db:
        set_family_context(db, api.family_id)
        rows = db.execute(text("SELECT first_name FROM person")).scalars().all()
        assert "Secret" not in rows and "Alpha" in rows
        set_family_context(db, None)
        assert db.execute(text("SELECT count(*) FROM person")).scalar() == 0
    # Un identifiant d'une autre famille renvoie 404.
    secret_id = other.get("/persons").json()["items"][0]["id"]
    assert api.get(f"/persons/{secret_id}").status_code == 404


def test_gedcom_export(api):
    ids = build_family(api)
    nji = api.post("/titles", {"name": "Nji", "precedence": 10}).json()
    api.post(f"/persons/{ids['a1']}/titles", {"title_id": nji["id"]})
    r = api.get("/export/gedcom")
    assert r.status_code == 200
    ged = r.text
    assert ged.startswith("0 HEAD") and ged.rstrip().endswith("0 TRLR")
    assert ged.count(" INDI") == 12
    assert "1 NAME Ngougouré //" in ged
    assert "1 TITL Nji" in ged
    assert "1 CHIL" in ged and "1 FAMS" in ged and "1 FAMC" in ged
    assert 'filename="Famille Test.ged"' in r.headers["content-disposition"]


def test_photo_upload(api):
    ids = build_family(api)
    r = api.c.post(
        f"/api/v1/persons/{ids['a']}/photo",
        headers=api.h,
        files={"file": ("photo.png", png_bytes(), "image/png")},
    )
    assert r.status_code == 200, r.text
    url = r.json()["photo_url"]
    assert url.endswith(".webp")
    path = url.split("/media/", 1)[1]
    img = api.c.get(f"/media/{path}")
    assert img.status_code == 200
    bad = api.c.post(
        f"/api/v1/persons/{ids['a']}/photo",
        headers=api.h,
        files={"file": ("x.png", b"pas une image", "image/png")},
    )
    assert bad.json()["detail"]["code"] == "invalid_image"


def test_stats(api):
    build_family(api)
    s = api.get("/stats").json()
    assert s["persons"] == 12
    assert s["generations"] == 4
    assert s["members"] == 1
