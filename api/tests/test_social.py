"""Phase 4 — vie sociale : fil, annonces, sondages, réactions, commentaires, stories,
modération, mémorial, anniversaires."""

from datetime import date, timedelta

from tests.conftest import build_family, join_as, png_bytes


def setup(client, api):
    ids = build_family(api)
    ali = join_as(client, api, "ali@example.com", "Ali Test", person_id=ids["a1"])
    return ids, ali


def test_post_comment_react(client, api):
    ids, ali = setup(client, api)
    post = ali.post("/posts", {"text": "Bienvenue au petit Adam !", "person_ids": [ids["a1c"]]})
    assert post.status_code == 201
    p = post.json()
    assert p["author"]["name"] == "Ali" and p["persons"][0]["first_name"] == "Adam"
    assert api.put(f"/posts/{p['id']}/reaction", {"emoji": "love"}).status_code == 204
    ali.put(f"/posts/{p['id']}/reaction", {"emoji": "clap"})
    api.put(f"/posts/{p['id']}/reaction", {"emoji": "pray"})  # remplace la précédente
    c = api.post(f"/posts/{p['id']}/comments", {"text": "Félicitations !"}).json()
    assert c["can_delete"] is True
    feed = ali.get("/feed").json()["items"]
    assert feed[0]["reactions"] == {"clap": 1, "pray": 1}
    assert feed[0]["my_reaction"] == "clap" and feed[0]["comments_count"] == 1
    # Ali ne supprime pas le commentaire de l'administrateur
    assert ali.delete(f"/comments/{c['id']}").status_code == 403
    assert ali.post("/posts", {"text": "  "}).json()["detail"]["code"] == "validation_error"


def test_announcements_are_pinned_and_reserved(client, api):
    ids, ali = setup(client, api)
    assert ali.post("/posts", {"kind": "announcement", "text": "AG"}).status_code == 403
    api.post(
        "/posts", {"kind": "announcement", "text": "Assemblée générale le 20 décembre à Foumban"}
    )
    ali.post("/posts", {"text": "Bonjour la famille"})
    feed = ali.get("/feed").json()["items"]
    assert feed[0]["kind"] == "announcement" and feed[0]["pinned"] is True


def test_poll(client, api):
    ids, ali = setup(client, api)
    assert (
        api.post("/posts", {"kind": "poll", "text": "Date ?", "poll_options": ["Seul"]}).status_code
        == 400
    )
    poll = api.post(
        "/posts",
        {"kind": "poll", "text": "Date de la réunion ?", "poll_options": ["20 déc.", "27 déc."]},
    ).json()
    first, second = poll["poll"]
    ali.post(f"/posts/{poll['id']}/vote", {"option_id": first["id"]})
    after = ali.post(
        f"/posts/{poll['id']}/vote", {"option_id": second["id"]}
    ).json()  # change d'avis
    assert [o["votes"] for o in after["poll"]] == [0, 1] and after["my_vote"] == second["id"]


def test_life_event_on_behalf_of_delegated_elder(client, api):
    ids, ali = setup(client, api)
    body = {
        "kind": "life_event",
        "life_event": "success",
        "text": "Diplôme !",
        "on_behalf_of": ids["husband"],
    }
    assert ali.post("/posts", body).status_code == 403
    me = next(m for m in api.get("/members").json() if m["full_name"] == "Ali Test")
    api.post(f"/persons/{ids['husband']}/delegates", {"membership_id": me["id"]})
    post = ali.post("/posts", body).json()
    assert post["on_behalf_of"]["first_name"] == "Époux" and post["life_event"] == "success"


def test_moderation(client, api):
    ids, ali = setup(client, api)
    post = ali.post("/posts", {"text": "Message déplacé"}).json()
    other = join_as(client, api, "bachir@example.com", "Bachir", person_id=ids["b1"])
    assert (
        other.post("/reports", {"post_id": post["id"], "reason": "Propos insultants"}).status_code
        == 201
    )
    assert ali.get("/reports").status_code == 403
    reports = api.get("/reports").json()
    assert reports[0]["excerpt"] == "Message déplacé"
    api.post(f"/reports/{reports[0]['id']}/resolve?hide=true")
    assert other.get("/feed").json()["items"] == []  # masquée pour les membres
    assert api.get("/feed").json()["items"][0]["hidden"] is True  # visible par la modération
    assert api.get("/reports").json() == []
    # lecture d'une publication seule : introuvable pour un membre une fois masquée
    assert other.get(f"/posts/{post['id']}").status_code == 404
    assert api.get(f"/posts/{post['id']}").json()["text"] == "Message déplacé"


def test_stories_expire(client, api):
    ids, ali = setup(client, api)
    url = ali.c.post(
        "/api/v1/uploads/image", headers=ali.h, files={"file": ("a.png", png_bytes(), "image/png")}
    ).json()["url"]
    ali.post("/stories", {"media_url": url, "caption": "Au village"})
    api.post("/stories", {"media_url": url})
    groups = ali.get("/stories").json()
    assert groups[0]["author"]["name"] == "Ali"  # les miennes d'abord
    assert len(groups) == 2
    # Une story expirée disparaît
    from app.core.db import SessionLocal, set_family_context
    from app.models import Story

    with SessionLocal() as db:
        set_family_context(db, api.family_id)
        for s in db.query(Story).all():
            s.expires_at = s.created_at - timedelta(minutes=1)
        db.commit()
    assert ali.get("/stories").json() == []


def test_memorial_and_birthdays(client, api):
    ids, ali = setup(client, api)
    assert (
        ali.post(f"/persons/{ids['a']}/memorial", {"text": "Repose en paix"}).json()["detail"][
            "code"
        ]
        == "not_deceased"
    )
    t = ali.post(f"/persons/{ids['root']}/memorial", {"text": "Merci pour tout, Mama"}).json()
    assert ali.get(f"/persons/{ids['root']}/memorial").json()[0]["text"] == "Merci pour tout, Mama"
    assert api.delete(f"/memorial/{t['id']}").status_code == 204

    today = date.today()
    soon = today + timedelta(days=5)
    api.patch(
        f"/persons/{ids['a2']}", {"birth_date": soon.replace(year=soon.year - 30).isoformat()}
    )
    b = ali.get("/birthdays", params={"days": 10}).json()
    assert b[0]["person"]["first_name"] == "Amina" and b[0]["in_days"] == 5 and b[0]["age"] == 30
