"""Réunion de deux familles : un foyer rejoint la grande famille."""

from tests.conftest import Api, build_family, join_as


def make_household(client, grand: Api):
    """Un foyer créé à part par Ali (déjà membre de la grande famille) : sa femme, leur fils."""
    ali = Api(client, "ali@example.com", "Ali Test")
    ali.create_family("Foyer d'Ali", first="Ali", sex="M")
    wife = ali.person("Zénabou", "F", spouse=ali.person_id)
    son = ali.person("Petit Ali", "M", parents=[ali.person_id, wife])
    nji = ali.post("/titles", {"name": "Nji", "precedence": 20}).json()
    ali.post(f"/persons/{son}/titles", {"title_id": nji["id"]})
    ali.patch("/families/current", {"root_person_id": ali.person_id})
    # Une cousine invitée dans le foyer seulement
    cousin = join_as(client, ali, "awa@example.com", "Awa Cousine")
    return ali, wife, son, cousin


def test_household_joins_grand_family(client, api):
    ids = build_family(api)
    # Ali est déjà membre de la grande famille (fiche « Ali », fils d'Alpha)
    inv = api.post("/invitations", {"person_id": ids["a1"]}).json()
    ali, wife, son, cousin = make_household(client, api)
    household_id = ali.family_id
    assert ali.post(f"/invitations/token/{inv['token']}/accept").status_code == 200
    api.post("/titles", {"name": "nji", "precedence": 20})  # même titre, casse différente

    req = api.post("/family-merges", {})
    assert req.status_code == 201
    token = req.json()["token"]
    assert "Famille Test" in req.json()["share_text"]

    preview = ali.get(f"/family-merges/token/{token}").json()
    assert preview["valid"] and preview["target_family_name"] == "Famille Test"

    # Seul l'administrateur de la famille source confirme, depuis sa famille.
    ali.family_id = household_id
    assert cousin.post(f"/family-merges/token/{token}/accept").status_code == 403
    r = ali.post(f"/family-merges/token/{token}/accept")
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["merged_accounts"] == 1  # Ali : une seule fiche
    assert result["new_members"] == 1  # Awa la cousine
    assert result["persons"] == 4  # Ali, sa femme, son fils, la fiche de la cousine

    # Dans la grande famille : la femme et le fils d'Ali sont rattachés à sa fiche existante.
    ali_detail = api.get(f"/persons/{ids['a1']}").json()
    assert {s["person"]["first_name"] for s in ali_detail["spouses"]} == {"Zénabou"}
    child = next(c for c in ali_detail["children"] if c["person"]["first_name"] == "Petit Ali")
    assert [t["name"] for t in child["person"]["titles"]] == ["nji"]  # titre regroupé
    assert len(api.get("/titles").json()) == 1
    # La cousine est membre de la grande famille ; Ali garde son rôle d'origine dans la grande.
    members = {m["full_name"]: m["role"] for m in api.get("/members").json()}
    assert members["Awa Cousine"] == "member" and members["Ali Test"] == "member"

    # Le foyer a disparu des listes et n'est plus accessible.
    names = [f["name"] for f in ali.get("/families").json()]
    assert names == ["Famille Test"]
    gone = ali.get("/persons")
    assert gone.status_code == 410 and gone.json()["detail"]["code"] == "family_merged"
    # Le code ne sert qu'une fois.
    assert ali.post(f"/family-merges/token/{token}/accept").status_code in (400, 410)


def test_merge_admin_becomes_branch_head(client, api):
    build_family(api)
    other = Api(client, "chef@example.com", "Chef Foyer")
    other.create_family("Autre foyer", first="Chef", sex="M")
    other.person("Fils", "M", parents=[other.person_id])
    token = api.post("/family-merges", {}).json()["token"]
    r = other.post(f"/family-merges/token/{token}/accept").json()
    assert r["new_members"] == 1 and r["persons"] == 2
    m = next(x for x in api.get("/members").json() if x["full_name"] == "Chef Foyer")
    assert m["role"] == "branch_head"
    # Il peut modifier les siens, pas le reste de la grande famille.
    other.family_id = r["target_family_id"]
    son = other.get("/persons", params={"q": "Fils"}).json()["items"][0]["id"]
    assert other.patch(f"/persons/{son}", {"village": "Foumban"}).status_code == 200


def test_cannot_merge_into_itself_or_twice(client, api):
    build_family(api)
    token = api.post("/family-merges", {}).json()["token"]
    assert (
        api.post(f"/family-merges/token/{token}/accept").json()["detail"]["code"] == "same_family"
    )
    assert api.get("/family-merges/token/inconnu").status_code == 404
