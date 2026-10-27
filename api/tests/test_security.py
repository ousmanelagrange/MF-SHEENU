"""Tests de sécurité : isolement des familles sur toutes les routes, authentification
(débit, verrouillage, rotation des jetons, durée constante), médias privés, idempotence,
en-têtes, taille des requêtes, falsification de jetons, supervision réservée à l'opérateur.

Le test central, `test_no_route_leaks_another_family`, parcourt TOUTES les routes de l'API
(lues dans le schéma OpenAPI) avec les identifiants d'une autre famille : aucune ne doit
renvoyer ni modifier ses données.
"""

import json
import re
import time
import uuid

import jwt
import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import SessionLocal, set_family_context
from app.main import app
from app.security import ratelimit
from tests.conftest import Api, build_family, join_as, png_bytes

SECRET_A = "SECRET-FAMILLE-A-7f3e"  # marqueur placé partout dans la famille A


# ---------- Construction d'une famille A complète ----------


def upload(client, who: Api) -> str:
    files = {"file": ("p.png", png_bytes(), "image/png")}
    return client.post("/api/v1/uploads/image", files=files, headers=who.h).json()["url"]


def family_a(client) -> tuple[Api, dict]:
    """Une famille avec au moins un objet de chaque sorte, et l'identifiant de chacun."""
    a = Api(client, "a-admin@example.com", "Admin Famille A")
    a.create_family(f"Famille A {SECRET_A}")
    ids = build_family(a)
    me = a.person_id
    pid = ids["a"]
    a.patch(f"/persons/{pid}", {"biography": SECRET_A})
    member = join_as(client, a, "a-membre@example.com", "Membre Famille A", person_id=ids["a1"])
    found = {"person_id": pid, "member": member}
    found["member_id"] = next(m["id"] for m in a.get("/members").json() if m["role"] == "member")
    found["link_id"] = a.post(
        "/relations/parent-child",
        {"parent_id": ids["b"], "child_id": ids["a2"], "kind": "adoptive"},
    ).json()["id"]
    found["union_id"] = a.post(
        "/unions", {"person_a_id": ids["b1"], "person_b_id": ids["a2"]}
    ).json()["id"]
    found["title_id"] = a.post("/titles", {"name": f"Nji {SECRET_A}"}).json()["id"]
    found["holding_id"] = a.post(f"/persons/{pid}/titles", {"title_id": found["title_id"]}).json()[
        "id"
    ]
    found["invitation_id"] = a.post("/invitations", {"note": SECRET_A}).json()["id"]
    found["delegation_id"] = a.post(
        f"/persons/{ids['root']}/delegates", {"membership_id": found["member_id"]}
    ).json()["id"]
    found["proposal_id"] = member.post(
        "/proposals",
        {
            "kind": "create_person",
            "payload": {"first_name": SECRET_A, "sex": "M", "parent_ids": [ids["b"]]},
        },
    ).json()["id"]
    media = upload(client, a)
    found["media"] = media
    post = a.post("/posts", {"text": SECRET_A, "media": [media]}).json()
    found["post_id"] = post["id"]
    poll = a.post(
        "/posts", {"kind": "poll", "text": SECRET_A, "poll_options": ["oui", "non"]}
    ).json()
    found["poll_id"], found["option_id"] = poll["id"], poll["poll"][0]["id"]
    found["comment_id"] = member.post(f"/posts/{post['id']}/comments", {"text": SECRET_A}).json()[
        "id"
    ]
    found["story_id"] = a.post("/stories", {"media_url": media, "caption": SECRET_A}).json()["id"]
    found["report_id"] = member.post(
        "/reports", {"post_id": post["id"], "reason": SECRET_A}
    ).json()["id"]
    found["message_id"] = a.post(f"/persons/{ids['root']}/memorial", {"text": SECRET_A}).json()[
        "id"
    ]
    found["narrative_id"] = a.post("/narratives", {"title": SECRET_A, "person_ids": [pid]}).json()[
        "id"
    ]
    found["text_id"] = member.post(
        f"/narratives/{found['narrative_id']}/texts", {"layer": "fr", "text": SECRET_A}
    ).json()["id"]
    found["album_id"] = a.post("/albums", {"title": SECRET_A}).json()["id"]
    found["photo_id"] = a.post(
        f"/albums/{found['album_id']}/photos",
        {"url": media, "caption": SECRET_A, "person_ids": [pid]},
    ).json()["id"]
    found["scale_id"] = a.post(
        "/contributions/scales", {"name": f"Barème {SECRET_A}", "default_amount": 5000}
    ).json()["id"]
    event = a.post("/contributions/events", {"title": SECRET_A, "kind": "mourning"}).json()
    found["event_id"] = event["id"]
    a.post(f"/contributions/events/{event['id']}/dues", {"person_id": pid, "amount": 5000})
    dues = a.get(f"/contributions/events/{event['id']}/dues").json()
    found["due_id"] = dues[0]["due_id"]
    found["payment_id"] = member.post(
        f"/contributions/events/{event['id']}/payments",
        {"person_id": pid, "amount": 1000, "reference": SECRET_A},
    ).json()["id"]
    token = a.post("/join-link").json()["link"].rsplit("/", 1)[1]
    visitor = Api(client, "a-visiteur@example.com", "Visiteur Famille A")
    visitor.post(f"/join/{token}", {"first_name": SECRET_A, "lineage": SECRET_A})
    found["request_id"] = a.get("/join-requests").json()[0]["id"]
    found["session_id"] = a.get("/auth/sessions").json()[0]["id"]
    found["user_id"] = a.get("/auth/me").json()["id"]
    found["family_id"] = a.family_id
    found["me"] = me
    return a, found


def snapshot(a: Api, f: dict) -> str:
    """État lisible de la famille A, pour vérifier que rien n'a bougé."""
    parts = [
        a.get(f"/persons/{f['person_id']}").json(),
        a.get("/feed").json()["items"],
        a.get(f"/posts/{f['post_id']}/comments").json(),
        a.get(f"/narratives/{f['narrative_id']}").json(),
        a.get(f"/narratives/{f['narrative_id']}/texts").json(),
        a.get(f"/albums/{f['album_id']}").json(),
        a.get(f"/contributions/events/{f['event_id']}/payments").json(),
        a.get(f"/contributions/events/{f['event_id']}/dues").json(),
        a.get("/proposals", params={"view": "all", "status": "any"}).json(),
        a.get("/join-requests").json(),
        a.get("/titles").json(),
        a.get("/stats").json(),
    ]
    # Les adresses signées changent d'une heure à l'autre : on les retire de la comparaison
    return re.sub(r"\?exp=\d+&sig=[\w-]+", "", json.dumps(parts, sort_keys=True, default=str))


# ---------- Isolement des familles sur toutes les routes ----------

PATHS = app.openapi()["paths"]
PUBLIC = (
    "/api/v1/auth/",
    "/api/v1/join/{token}",
    "/api/v1/invitations/token/",
    "/api/v1/family-merges/token/",
    "/api/v1/webhooks/",
)


def test_no_route_leaks_another_family(client):
    a, f = family_a(client)
    before = snapshot(a, f)
    b = Api(client, "b-admin@example.com", "Admin Famille B")
    b.create_family("Famille B")
    a_ids = {str(v) for k, v in f.items() if isinstance(v, str) and k not in ("media",)}
    checked = 0
    for path, ops in PATHS.items():
        if not path.startswith("/api/v1") or path.startswith(PUBLIC):
            continue
        url = path.removeprefix("/api/v1")
        for name in re.findall(r"{(\w+)}", url):
            url = url.replace("{" + name + "}", str(f.get(name, uuid.uuid4())))
        for method in ops:
            for family in (b.family_id, f["family_id"]):  # sa propre famille, puis celle de A
                b.family_id = family
                r = client.request(method.upper(), f"/api/v1{url}", headers=b.h, json={})
                checked += 1
                body = r.text
                assert SECRET_A not in body, (
                    f"{method.upper()} {path} (famille {family}) expose la famille A"
                )
                if r.status_code < 300:
                    # Une réponse réussie ne doit contenir aucun identifiant de la famille A
                    leaked = [i for i in a_ids if i in body]
                    assert not leaked, (
                        f"{method.upper()} {path} (famille {family}) renvoie {leaked}"
                    )
    b.family_id = None
    assert checked > 200
    assert snapshot(a, f) == before, "une route a modifié la famille A"


def test_cross_family_writes_with_valid_bodies(client):
    """Les mêmes attaques avec des corps de requête valides (sans erreur de format qui masquerait
    un défaut de contrôle)."""
    a, f = family_a(client)
    before = snapshot(a, f)
    b = Api(client, "b-admin@example.com", "Admin Famille B")
    b.create_family("Famille B")
    mine = b.person("Bob", "M")
    album = b.post("/albums", {"title": "Album B"}).json()["id"]
    attacks = [
        ("PATCH", f"/persons/{f['person_id']}", {"village": "piraté"}),
        ("DELETE", f"/persons/{f['person_id']}", None),
        ("POST", "/relations/parent-child", {"parent_id": mine, "child_id": f["person_id"]}),
        ("POST", "/unions", {"person_a_id": mine, "person_b_id": f["person_id"]}),
        ("POST", "/persons", {"first_name": "Intrus", "parent_ids": [f["person_id"]]}),
        ("POST", f"/persons/{f['person_id']}/titles", {"title_id": f["title_id"]}),
        ("POST", f"/posts/{f['post_id']}/comments", {"text": "x"}),
        ("PUT", f"/posts/{f['post_id']}/reaction", {"emoji": "like"}),
        ("POST", f"/posts/{f['poll_id']}/vote", {"option_id": f["option_id"]}),
        ("PATCH", f"/posts/{f['post_id']}", {"hidden": True}),
        ("POST", "/posts", {"text": "x", "person_ids": [f["person_id"]]}),
        ("POST", "/posts", {"text": "x", "media": [f["media"]]}),
        ("POST", "/stories", {"media_url": f["media"]}),
        ("POST", f"/albums/{album}/photos", {"url": f["media"]}),
        ("POST", "/reports", {"post_id": f["post_id"], "reason": "abus"}),
        ("POST", f"/persons/{f['person_id']}/memorial", {"text": "x"}),
        ("POST", f"/narratives/{f['narrative_id']}/texts", {"layer": "fr", "text": "x"}),
        ("POST", f"/narrative-texts/{f['text_id']}/validate", {}),
        ("PATCH", f"/album-photos/{f['photo_id']}", {"person_ids": []}),
        ("POST", f"/contributions/payments/{f['payment_id']}/validate", {}),
        (
            "POST",
            f"/contributions/events/{f['event_id']}/payments",
            {"person_id": f["person_id"], "amount": 1},
        ),
        ("POST", f"/contributions/events/{f['event_id']}/reminders", {}),
        ("PATCH", f"/contributions/dues/{f['due_id']}", {"exempt": True}),
        ("POST", f"/proposals/{f['proposal_id']}/accept", {}),
        ("POST", f"/join-requests/{f['request_id']}/accept", {}),
        ("POST", f"/persons/{f['person_id']}/delegates", {"membership_id": f["member_id"]}),
        ("PATCH", f"/members/{f['member_id']}", {"role": "admin"}),
        ("PATCH", "/families/current", {"root_person_id": f["person_id"]}),
        ("DELETE", f"/auth/sessions/{f['session_id']}", None),
    ]
    for method, path, body in attacks:
        r = client.request(method, f"/api/v1{path}", headers=b.h, json=body)
        assert r.status_code in (400, 403, 404, 409, 422), (
            f"{method} {path} → {r.status_code} {r.text[:200]}"
        )
        assert SECRET_A not in r.text
    assert snapshot(a, f) == before


def test_rls_blocks_even_raw_sql(client):
    """Défense en profondeur : même une requête SQL sans filtre ne voit que la famille du contexte."""
    a, f = family_a(client)
    b = Api(client, "b-admin@example.com", "Admin Famille B")
    b.create_family("Famille B")
    with SessionLocal() as db:
        set_family_context(db, uuid.UUID(b.family_id))
        for table in (
            "person",
            "post",
            "comment",
            "narrative",
            "narrative_text",
            "album_photo",
            "contribution_payment",
            "notification",
            "audit_log",
        ):
            leaked = db.execute(
                text(f"SELECT count(*) FROM {table} WHERE family_id = :f"), {"f": f["family_id"]}
            ).scalar()  # noqa: S608
            assert leaked == 0, table
        set_family_context(db, None)
        assert db.execute(text("SELECT count(*) FROM person")).scalar() == 0  # sans contexte : rien


# ---------- Authentification ----------


@pytest.fixture
def limits(monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit", True)
    ratelimit.reset()
    yield
    ratelimit.reset()


def login(client, ident, password):
    return client.post("/api/v1/auth/login", json={"login": ident, "password": password})


def test_lockout_after_failures(client):
    Api(client, "cible@example.com", "Cible Test")
    for _ in range(5):
        assert login(client, "cible@example.com", "mauvais-mot").status_code == 401
    # Même le bon mot de passe est refusé pendant le verrouillage
    r = login(client, "cible@example.com", "motdepasse123")
    assert r.status_code == 429 and r.json()["detail"]["code"] == "account_locked"
    with SessionLocal() as db:
        kinds = [k for (k,) in db.execute(text("SELECT kind FROM security_event"))]
    assert kinds.count("login_failed") == 5 and "login_locked" in kinds


def test_login_rate_limit_per_ip(client, limits):
    codes = [login(client, f"inconnu{i}@example.com", "x" * 8).status_code for i in range(12)]
    assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]


def test_same_duration_whether_account_exists(client):
    Api(client, "existe@example.com", "Compte Existant")

    def timed(ident: str) -> float:
        start = time.perf_counter()
        login(client, ident, "mauvais-mot-de-passe")
        return time.perf_counter() - start

    exists = min(timed("existe@example.com") for _ in range(3))
    missing = min(timed("absent@example.com") for _ in range(3))
    assert 0.5 < exists / missing < 2, (exists, missing)


def test_refresh_rotation_and_reuse_detection(client):
    user = Api(client, "rotation@example.com", "Rotation Test")
    tokens = login(client, "rotation@example.com", "motdepasse123").json()
    first = tokens["refresh_token"]
    second = client.post("/api/v1/auth/refresh", json={"refresh_token": first}).json()[
        "refresh_token"
    ]
    third = client.post("/api/v1/auth/refresh", json={"refresh_token": second}).json()[
        "refresh_token"
    ]
    # Rejouer le premier jeton (copié par un voleur) ferme toutes les sessions du compte
    stolen = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert stolen.status_code == 401 and stolen.json()["detail"]["code"] == "session_revoked"
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": third}).status_code == 401
    assert user.get("/auth/me").status_code == 401  # même les jetons d'accès tombent
    with SessionLocal() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM security_event WHERE kind = 'refresh_reuse'")
            ).scalar()
            == 1
        )


def test_password_change_closes_other_sessions(client):
    phone = Api(client, "mdp@example.com", "Changement Test")
    laptop = login(client, "mdp@example.com", "motdepasse123").json()
    r = client.post(
        "/api/v1/auth/password",
        json={"current_password": "motdepasse123", "new_password": "une phrase bien longue 2026"},
        headers=phone.h,
    )
    assert r.status_code == 200
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": laptop["refresh_token"]}
        ).status_code
        == 401
    )
    assert login(client, "mdp@example.com", "une phrase bien longue 2026").status_code == 200


def test_weak_passwords_refused(client):
    for pw in ("password", "azertyuiop", "aaaaaaaaaa", "kouamekouame1"):
        r = client.post(
            "/api/v1/auth/register",
            json={"full_name": "Kouame Test", "email": "k@example.com", "password": pw},
        )
        assert r.status_code == 400 and r.json()["detail"]["code"] == "weak_password", pw


def test_forged_tokens_refused(client):
    user = Api(client, "jeton@example.com", "Jeton Test")
    payload = jwt.decode(user.token, options={"verify_signature": False})
    forged = [
        jwt.encode({**payload, "sub": str(uuid.uuid4())}, "mauvais-secret", algorithm="HS256"),
        jwt.encode({**payload}, key="", algorithm="none") if hasattr(jwt, "encode") else "x",
        jwt.encode(
            {**payload, "exp": int(time.time()) - 10}, get_settings().jwt_secret, algorithm="HS256"
        ),
        jwt.encode({**payload, "typ": "refresh"}, get_settings().jwt_secret, algorithm="HS256"),
        user.token[:-4] + "abcd",
    ]
    for token in forged:
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401, token


# ---------- Médias, requêtes, en-têtes ----------


def test_media_needs_valid_signature(client):
    a, f = family_a(client)
    path = f["media"].split("/media/", 1)[1]
    assert client.get(f"/media/{path}").status_code == 200
    key = path.split("?")[0]
    assert client.get(f"/media/{key}").status_code == 403
    assert (
        client.get(f"/media/{key}?exp=9999999999&sig=AAAAAAAAAAAAAAAAAAAAAAAA").status_code == 403
    )
    assert client.get("/media/../../etc/passwd?exp=9999999999&sig=x").status_code in (403, 404)


def test_security_headers(client):
    user = Api(client, "entetes@example.com", "Entetes Test")
    r = user.get("/auth/me")
    for header, value in (
        ("x-content-type-options", "nosniff"),
        ("x-frame-options", "DENY"),
        ("referrer-policy", "no-referrer"),
        ("cache-control", "no-store"),
        ("content-security-policy", "default-src 'none'; frame-ancestors 'none'"),
    ):
        assert r.headers.get(header) == value, header
    assert r.headers.get("x-request-id")


def test_oversized_bodies_refused(client):
    user = Api(client, "lourd@example.com", "Lourd Test")
    user.create_family()
    huge = {"text": "x" * (1024 * 1024 + 10)}
    assert client.post("/api/v1/posts", json=huge, headers=user.h).status_code == 413


def test_idempotent_replay(client):
    user = Api(client, "idem@example.com", "Idem Test")
    user.create_family()
    headers = {**user.h, "Idempotency-Key": "envoi-hors-ligne-1"}
    first = client.post("/api/v1/posts", json={"text": "Publié hors ligne"}, headers=headers)
    again = client.post("/api/v1/posts", json={"text": "Publié hors ligne"}, headers=headers)
    assert first.status_code == again.status_code == 201
    assert (
        first.json()["id"] == again.json()["id"]
        and again.headers.get("idempotent-replayed") == "true"
    )
    assert len(user.get("/feed").json()["items"]) == 1
    other = client.post("/api/v1/posts", json={"text": "Autre chose"}, headers=headers)
    assert other.status_code == 422 and other.json()["detail"]["code"] == "idempotency_mismatch"


def test_logs_are_append_only(client):
    user = Api(client, "journal@example.com", "Journal Test")
    user.create_family()
    login(client, "journal@example.com", "faux-mot-de-passe")  # un événement de sécurité existe
    with SessionLocal() as db:
        set_family_context(db, uuid.UUID(user.family_id))
        with pytest.raises(Exception, match="ajout seul"):
            db.execute(text("DELETE FROM audit_log"))
        db.rollback()
        with pytest.raises(Exception, match="ajout seul"):
            db.execute(text("UPDATE security_event SET kind = 'effacé'"))


# ---------- Supervision ----------


def make_operator(email: str) -> None:
    with SessionLocal() as db:
        db.execute(
            text("UPDATE app_user SET is_platform_admin = true WHERE email = :e"), {"e": email}
        )
        db.commit()


def test_platform_reserved_to_operator(client):
    user = Api(client, "simple@example.com", "Simple Membre")
    for path in (
        "/platform/overview",
        "/platform/events",
        "/platform/users",
        "/platform/families",
        "/platform/audit",
    ):
        assert user.get(path).status_code == 403


def test_platform_supervision_without_family_content(client):
    a, f = family_a(client)
    op = Api(client, "operateur@example.com", "Operateur Plateforme")
    make_operator("operateur@example.com")
    login(client, "a-admin@example.com", "faux-mot-de-passe")
    overview = op.get("/platform/overview").json()
    assert overview["health"]["rls_enforced"] is True
    assert overview["users"]["total"] >= 4 and overview["families"]["total"] == 1
    families = op.get("/platform/families").json()
    assert families[0]["persons"] >= 12
    # L'opérateur voit des nombres et des comptes, jamais le contenu des familles
    for path in ("/platform/families", "/platform/users", "/platform/events", "/platform/overview"):
        body = op.get(path).text
        assert "Ngougouré" not in body and SECRET_A not in body.replace(
            f"Famille A {SECRET_A}", ""
        ), path
    # Il ne peut pas non plus ouvrir la famille
    op.family_id = f["family_id"]
    assert op.get("/persons").status_code == 403
    op.family_id = None
    # Suspendre un compte : déconnexion immédiate, action journalisée
    target = f["member"]
    member_id = next(u["id"] for u in op.get("/platform/users", params={"q": "a-membre"}).json())
    assert (
        op.post(f"/platform/users/{member_id}/disable", {"reason": "Compte piraté"}).status_code
        == 204
    )
    assert target.get("/auth/me").status_code == 401
    assert login(client, "a-membre@example.com", "motdepasse123").status_code == 401
    actions = [x["action"] for x in op.get("/platform/audit").json()]
    assert "disable_user" in actions and "view_users" in actions
    kinds = {e["kind"] for e in op.get("/platform/events").json()}
    assert {"login_failed", "account_disabled"} <= kinds


def test_unexpected_errors_are_contained():
    """Une erreur imprévue : réponse 500 propre (sans détail technique), incident journalisé."""
    from fastapi.testclient import TestClient

    def boom() -> None:
        raise RuntimeError("détail interne qui ne doit pas sortir")

    app.add_api_route("/api/v1/__boom", boom)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/v1/__boom")
        assert r.status_code == 500
        assert r.json()["detail"]["code"] == "server_error"
        assert "détail interne" not in r.text and "Traceback" not in r.text
        with SessionLocal() as db:
            assert (
                db.execute(
                    text("SELECT count(*) FROM security_event WHERE kind = 'server_error'")
                ).scalar()
                == 1
            )
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", "") != "/api/v1/__boom"
        ]
