"""Phase 2 — gouvernance : propositions, validation par le chef de branche, délégations."""

from tests.conftest import build_family, join_as


def setup_branch(client, api):
    """Famille de test + un chef de la branche « Beta » + Ali, membre de la branche « Alpha »."""
    ids = build_family(api)
    head = join_as(client, api, "head@example.com", "Chef Beta", role="branch_head")
    m = next(x for x in api.get("/members").json() if x["full_name"] == "Chef Beta")
    api.patch(f"/members/{m['id']}", {"branch_person_id": ids["b"]})
    ali = join_as(client, api, "ali@example.com", "Ali Test", person_id=ids["a1"])
    return ids, head, ali


def test_member_proposes_and_branch_head_accepts(client, api):
    ids, head, ali = setup_branch(client, api)
    # Ali ne peut pas ajouter directement un enfant à sa tante Beta…
    direct = ali.post("/persons", {"first_name": "Nouveau", "parent_ids": [ids["b"]]})
    assert direct.json()["detail"]["code"] == "out_of_scope"
    # … il le propose.
    r = ali.post(
        "/proposals",
        {
            "kind": "create_person",
            "payload": {"first_name": "Nouveau", "sex": "M", "parent_ids": [ids["b"]]},
            "message": "Né le mois dernier à Douala",
        },
    )
    assert r.status_code == 201, r.text
    prop = r.json()
    assert prop["summary"] == "Ajouter Nouveau comme enfant de Beta"
    assert prop["status"] == "pending"

    # Compteurs : le chef de la branche Beta la voit, Ali la suit.
    assert head.get("/proposals/counts").json() == {"to_review": 1, "mine_pending": 0}
    assert ali.get("/proposals/counts").json() == {"to_review": 0, "mine_pending": 1}
    assert [p["id"] for p in head.get("/proposals").json()] == [prop["id"]]
    assert ali.get("/proposals").json() == []
    assert len(ali.get("/proposals", params={"view": "mine"}).json()) == 1

    # Ali ne peut pas valider sa propre proposition.
    assert ali.post(f"/proposals/{prop['id']}/accept", {}).status_code == 403

    done = head.post(f"/proposals/{prop['id']}/accept", {"note": "Bienvenue"}).json()
    assert done["status"] == "accepted"
    assert done["reviewer_name"] == "Chef Beta"
    child = api.get(f"/persons/{done['result_id']}").json()
    assert child["first_name"] == "Nouveau"
    assert child["parents"][0]["person"]["id"] == ids["b"]
    # Traitée une seule fois
    again = head.post(f"/proposals/{prop['id']}/accept", {})
    assert again.json()["detail"]["code"] == "already_reviewed"


def test_branch_head_cannot_review_outside_branch(client, api):
    ids, head, ali = setup_branch(client, api)
    # Proposition sur la branche Alpha, faite par un membre de la branche Beta
    beta_member = join_as(client, api, "bachir@example.com", "Bachir", person_id=ids["b1"])
    prop = beta_member.post(
        "/proposals",
        {
            "kind": "update_person",
            "payload": {"person_id": ids["a"], "changes": {"village": "Koutaba"}},
        },
    ).json()
    assert prop["summary"] == "Modifier la fiche de Alpha (village)"
    assert head.post(f"/proposals/{prop['id']}/accept", {}).status_code == 403
    assert head.get("/proposals/counts").json()["to_review"] == 0
    # L'administrateur peut tout valider.
    assert api.post(f"/proposals/{prop['id']}/accept", {}).status_code == 200
    assert api.get(f"/persons/{ids['a']}").json()["village"] == "Koutaba"


def test_reject_requires_note_and_withdraw(client, api):
    ids, head, ali = setup_branch(client, api)
    prop = ali.post(
        "/proposals",
        {"kind": "add_union", "payload": {"person_a_id": ids["b"], "person_b_id": ids["a1c"]}},
    ).json()
    assert (
        head.post(f"/proposals/{prop['id']}/reject", {}).json()["detail"]["code"] == "note_required"
    )
    r = head.post(f"/proposals/{prop['id']}/reject", {"note": "Information inexacte"}).json()
    assert r["status"] == "rejected" and r["review_note"] == "Information inexacte"

    other = ali.post(
        "/proposals", {"kind": "archive_person", "payload": {"person_id": ids["b1c"]}}
    ).json()
    assert head.post(f"/proposals/{other['id']}/withdraw").status_code == 403
    assert ali.post(f"/proposals/{other['id']}/withdraw").json()["status"] == "withdrawn"


def test_invalid_or_impossible_proposals(client, api):
    ids, head, ali = setup_branch(client, api)
    bad = ali.post("/proposals", {"kind": "add_parent_child", "payload": {"parent_id": "x"}})
    assert bad.json()["detail"]["code"] == "validation_error"
    # Une boucle est refusée au moment de l'acceptation, et la proposition reste en attente.
    prop = ali.post(
        "/proposals",
        {"kind": "add_parent_child", "payload": {"parent_id": ids["b1c"], "child_id": ids["b"]}},
    ).json()
    r = head.post(f"/proposals/{prop['id']}/accept", {})
    assert r.json()["detail"]["code"] == "cycle_detected"
    pending = head.get("/proposals").json()
    assert pending[0]["status"] == "pending"


def test_new_person_as_parent_of_existing_children(api):
    ids = build_family(api)
    r = api.post("/persons", {"first_name": "Aïeul", "sex": "M", "child_ids": [ids["husband"]]})
    assert r.status_code == 201
    assert r.json()["children"][0]["person"]["id"] == ids["husband"]
    # La règle des deux parents biologiques s'applique aussi ici.
    api.post("/persons", {"first_name": "Aïeule", "sex": "F", "child_ids": [ids["husband"]]})
    third = api.post("/persons", {"first_name": "Trop", "child_ids": [ids["husband"]]})
    assert third.json()["detail"]["code"] == "too_many_parents"


def test_delegation_lets_member_manage_an_elder(client, api):
    ids, head, ali = setup_branch(client, api)
    # Ali ne peut pas modifier la fiche de son grand-père…
    assert ali.patch(f"/persons/{ids['husband']}", {"village": "Foumban"}).status_code == 403
    me = next(x for x in api.get("/members").json() if x["full_name"] == "Ali Test")
    # … un simple membre ne peut pas déléguer…
    assert (
        ali.post(f"/persons/{ids['husband']}/delegates", {"membership_id": me["id"]}).status_code
        == 403
    )
    # … mais l'administrateur lui confie la fiche.
    d = api.post(f"/persons/{ids['husband']}/delegates", {"membership_id": me["id"]})
    assert d.status_code == 201 and d.json()["member_name"] == "Ali Test"
    assert ali.patch(f"/persons/{ids['husband']}", {"village": "Foumban"}).status_code == 200
    assert ali.get(f"/persons/{ids['husband']}").json()["can_edit"] is True
    assert len(api.get(f"/persons/{ids['husband']}/delegates").json()) == 1
    # Retrait de la délégation
    assert api.delete(f"/delegations/{d.json()['id']}").status_code == 204
    assert ali.patch(f"/persons/{ids['husband']}", {"village": "X"}).status_code == 403
