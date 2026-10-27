"""Simulation de bout en bout avec de nombreux utilisateurs simultanés.

    python -m tests.load.simulate --url http://localhost:8100 --families 3 --members 20 --seconds 60

À lancer contre une instance dédiée et une base vide (jamais la production) :
voir docs/07-tests-et-securite.md. Déroulé :

1. mise en place : N familles, chacune avec un administrateur, un trésorier, une secrétaire,
   un chef de branche et des membres, un arbre, une collecte, un sondage, des récits ;
2. charge : tous les comptes agissent en même temps pendant `seconds` secondes (lectures,
   publications, commentaires, réactions, votes, paiements, propositions, relectures…) ;
   s'y ajoutent des courses provoquées (deux responsables valident la même chose au même
   instant, double appui, envoi rejoué avec la même clé) et des intrus qui visent les
   identifiants d'une autre famille ;
3. vérification des invariants : aucune erreur serveur, aucune fuite entre familles, un vote
   et une réaction au plus par personne, totaux des collectes justes, chaque proposition
   appliquée une seule fois, chaque envoi rejoué créé une seule fois.

Le rapport (latences, débit, invariants) est écrit en JSON et résumé à l'écran.
"""

import argparse
import asyncio
import json
import random
import time
import uuid
from collections import Counter, defaultdict

import httpx

PASSWORD = "une phrase de test 2026"


class Stats:
    def __init__(self) -> None:
        self.latency: dict[str, list[float]] = defaultdict(list)
        self.status: Counter = Counter()
        self.by_status: Counter = Counter()  # (action, statut)
        self.errors: list[str] = []
        self.leaks: list[str] = []
        self.transport_retries = 0  # connexion coupée par le réseau, renvoyée une fois
        self.intrusions = 0

    def record(self, label: str, r: httpx.Response, ms: float) -> None:
        self.latency[label].append(ms)
        self.status[r.status_code // 100 * 100] += 1
        self.by_status[(label, r.status_code)] += 1
        if r.status_code >= 500:
            self.errors.append(f"{label} {r.status_code} {r.text[:200]}")


class User:
    def __init__(self, client: httpx.AsyncClient, stats: Stats, email: str, name: str) -> None:
        self.c, self.stats, self.email, self.name = client, stats, email, name
        self.token = ""
        self.family = ""
        self.person = ""
        self.role = "member"

    @property
    def headers(self) -> dict:
        h = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        if self.family:
            h["X-Family-Id"] = self.family
        return h

    async def call(self, label: str, method: str, path: str, **kw) -> httpx.Response:
        headers = {**self.headers, **kw.pop("headers", {})}
        start = time.perf_counter()
        try:
            r = await self.c.request(method, f"/api/v1{path}", headers=headers, **kw)
        except (httpx.ReadError, httpx.RemoteProtocolError, httpx.ConnectError):
            # Connexion réutilisée au moment où le serveur la fermait : on renvoie, comme un
            # navigateur (les écritures portent une clé d'idempotence quand elles le doivent)
            self.stats.transport_retries += 1
            r = await self.c.request(method, f"/api/v1{path}", headers=headers, **kw)
        self.stats.record(label, r, (time.perf_counter() - start) * 1000)
        return r

    async def register(self) -> None:
        r = await self.call(
            "register",
            "POST",
            "/auth/register",
            json={"full_name": self.name, "email": self.email, "password": PASSWORD},
        )
        assert r.status_code == 201, r.text
        self.token = r.json()["access_token"]


async def setup_family(client, stats, index: int, members: int) -> dict:
    """Une famille complète, et la liste de ses comptes avec leur rôle."""
    tag = f"f{index}-{uuid.uuid4().hex[:6]}"
    admin = User(client, stats, f"admin-{tag}@charge-sheenu.example.com", f"Admin Famille {index}")
    await admin.register()
    r = await admin.call(
        "create_family",
        "POST",
        "/families",
        json={"name": f"Famille de charge {index}", "my_first_name": "Admin", "my_sex": "M"},
    )
    fam = r.json()
    admin.family, admin.person, admin.role = fam["id"], fam["person_id"], "admin"

    # Un arbre : 4 générations, quelques centaines de fiches au total pour 3 familles
    root = (
        await admin.call(
            "person",
            "POST",
            "/persons",
            json={"first_name": "Racine", "sex": "F", "is_living": False, "birth_year": 1880},
        )
    ).json()["id"]
    await admin.call("root", "PATCH", "/families/current", json={"root_person_id": root})
    generation = [root]
    persons = [root]
    for depth in range(3):
        nxt = []
        for parent in generation:
            for k in range(3):
                pid = (
                    await admin.call(
                        "person",
                        "POST",
                        "/persons",
                        json={
                            "first_name": f"G{depth + 2}-{k}",
                            "sex": random.choice("MF"),
                            "parent_ids": [parent],
                            "birth_year": 1910 + depth * 30,
                        },
                    )
                ).json()["id"]
                nxt.append(pid)
        generation = nxt
        persons += nxt

    # Les comptes : chacun relié à une fiche de la dernière génération
    users = [admin]
    roles = ["treasurer", "secretary", "branch_head"] + ["member"] * (members - 4)
    for i, role in enumerate(roles):
        person = generation[i % len(generation)]
        inv = (
            await admin.call(
                "invite", "POST", "/invitations", json={"role": role, "person_id": person}
            )
        ).json()
        u = User(
            client,
            stats,
            f"{role}{i}-{tag}@charge-sheenu.example.com",
            f"Membre {i} Famille {index}",
        )
        await u.register()
        accepted = await u.call(
            "accept_invitation", "POST", f"/invitations/token/{inv['token']}/accept"
        )
        assert accepted.status_code == 200, accepted.text
        u.family, u.person, u.role = fam["id"], accepted.json()["person_id"], role
        users.append(u)
    branch_head = next(u for u in users if u.role == "branch_head")
    await admin.call(
        "branch",
        "PATCH",
        f"/members/{(await admin.call('members', 'GET', '/members')).json()[3]['id']}",
        json={"branch_person_id": generation[0]},
    )

    event = (
        await admin.call(
            "event",
            "POST",
            "/contributions/events",
            json={"title": "Collecte de charge", "kind": "project"},
        )
    ).json()
    for u in users:
        await admin.call(
            "due",
            "POST",
            f"/contributions/events/{event['id']}/dues",
            json={"person_id": u.person, "amount": 10000},
        )
    poll = (
        await admin.call(
            "poll",
            "POST",
            "/posts",
            json={"kind": "poll", "text": "Sondage de charge", "poll_options": ["A", "B", "C"]},
        )
    ).json()
    narrative = (
        await admin.call(
            "narrative",
            "POST",
            "/narratives",
            json={"title": "Récit de charge", "person_ids": [root]},
        )
    ).json()
    return {
        "id": fam["id"],
        "users": users,
        "persons": persons,
        "event": event["id"],
        "poll": poll["id"],
        "options": [o["id"] for o in poll["poll"]],
        "narrative": narrative["id"],
        "branch_head": branch_head,
    }


async def member_loop(u: User, fam: dict, deadline: float, foreign: list[dict], made: dict) -> None:
    """Ce que fait un membre ordinaire, au hasard, jusqu'à la fin du temps imparti."""
    while time.monotonic() < deadline:
        action = random.choices(
            [
                "feed",
                "tree",
                "person",
                "search",
                "post",
                "comment",
                "react",
                "vote",
                "pay",
                "propose",
                "text",
                "notifications",
                "narratives",
                "intrude",
            ],
            weights=[14, 4, 10, 6, 5, 6, 8, 3, 3, 3, 2, 6, 3, 3],
        )[0]
        if action == "feed":
            await u.call("GET /feed", "GET", "/feed")
        elif action == "tree":
            await u.call("GET /tree", "GET", "/tree")
        elif action == "person":
            await u.call("GET /persons/{id}", "GET", f"/persons/{random.choice(fam['persons'])}")
        elif action == "search":
            await u.call(
                "GET /persons?q",
                "GET",
                "/persons",
                params={"q": random.choice(["G2", "G3", "Racine", "Membre"])},
            )
        elif action == "post":
            r = await u.call(
                "POST /posts", "POST", "/posts", json={"text": f"Nouvelle de {u.name}"}
            )
            if r.status_code == 201:
                made["posts"][fam["id"]].append(r.json()["id"])
        elif action == "comment" and made["posts"][fam["id"]]:
            await u.call(
                "POST /comments",
                "POST",
                f"/posts/{random.choice(made['posts'][fam['id']])}/comments",
                json={"text": "Bravo !"},
            )
        elif action == "react" and made["posts"][fam["id"]]:
            post = random.choice(made["posts"][fam["id"]])
            # Double appui : la même réaction envoyée deux fois en même temps
            body = {"emoji": random.choice(["like", "love", "pray", "clap"])}
            await asyncio.gather(
                *(
                    u.call("PUT /reaction", "PUT", f"/posts/{post}/reaction", json=body)
                    for _ in range(2)
                )
            )
        elif action == "vote":
            await asyncio.gather(
                *(
                    u.call(
                        "POST /vote",
                        "POST",
                        f"/posts/{fam['poll']}/vote",
                        json={"option_id": random.choice(fam["options"])},
                    )
                    for _ in range(2)
                )
            )
        elif action == "pay":
            ref = f"REF-{uuid.uuid4().hex[:10]}"
            # Envoi rejoué (application hors ligne qui resynchronise) : même clé, deux fois en même temps
            key = uuid.uuid4().hex
            body = {
                "person_id": u.person,
                "amount": random.choice([1000, 2500, 5000]),
                "reference": ref,
            }
            results = await asyncio.gather(
                *(
                    u.call(
                        "POST /payments",
                        "POST",
                        f"/contributions/events/{fam['event']}/payments",
                        json=body,
                        headers={"Idempotency-Key": key},
                    )
                    for _ in range(2)
                )
            )
            if any(r.status_code == 201 for r in results):
                made["payments"][fam["id"]].append(ref)
        elif action == "propose":
            marker = f"Proposée-{uuid.uuid4().hex[:8]}"
            r = await u.call(
                "POST /proposals",
                "POST",
                "/proposals",
                json={
                    "kind": "create_person",
                    "payload": {
                        "first_name": marker,
                        "sex": "U",
                        "parent_ids": [random.choice(fam["persons"])],
                    },
                },
            )
            if r.status_code == 201 and r.json().get("status") == "pending":
                made["proposals"][fam["id"]].append((r.json()["id"], marker))
        elif action == "text":
            await u.call(
                "POST /texts",
                "POST",
                f"/narratives/{fam['narrative']}/texts",
                json={"layer": random.choice(["fr", "en"]), "text": f"Version de {u.name}"},
            )
        elif action == "notifications":
            await u.call("GET /notifications", "GET", "/notifications")
        elif action == "narratives":
            await u.call("GET /narratives", "GET", "/narratives")
        elif action == "intrude":
            await intrude(u, random.choice(foreign))
        await asyncio.sleep(random.uniform(0.05, 0.3))


async def intrude(u: User, other: dict) -> None:
    """Un membre vise les identifiants d'une autre famille, avec sa famille puis avec l'autre."""
    targets = [
        ("GET", f"/persons/{random.choice(other['persons'])}", None),
        ("PATCH", f"/persons/{random.choice(other['persons'])}", {"village": "piraté"}),
        ("GET", f"/contributions/events/{other['event']}/dues", None),
        ("POST", f"/posts/{other['poll']}/vote", {"option_id": other["options"][0]}),
        ("GET", f"/narratives/{other['narrative']}", None),
    ]
    method, path, body = random.choice(targets)
    for family in (u.family, other["id"]):
        r = await u.call("intrusion", method, path, json=body, headers={"X-Family-Id": family})
        u.stats.intrusions += 1
        if r.status_code < 300:
            u.stats.leaks.append(f"{method} {path} famille {family} → {r.status_code}")


async def reviewer_loop(u: User, fam: dict, deadline: float, made: dict) -> None:
    """Responsables : relisent en même temps que les autres (courses volontaires)."""
    while time.monotonic() < deadline:
        if u.role in ("admin", "branch_head"):
            pending = [p for p in (await u.call("GET /proposals", "GET", "/proposals")).json()]
            for p in pending[:3]:
                await u.call(
                    "POST /proposals/accept", "POST", f"/proposals/{p['id']}/accept", json={}
                )
        if u.role in ("admin", "treasurer"):
            declared = (
                await u.call(
                    "GET /payments",
                    "GET",
                    f"/contributions/events/{fam['event']}/payments",
                    params={"status": "declared"},
                )
            ).json()
            for p in declared[:5]:
                await u.call(
                    "POST /payments/validate",
                    "POST",
                    f"/contributions/payments/{p['id']}/validate",
                    json={},
                )
        if u.role in ("admin", "secretary", "branch_head"):
            texts = (
                await u.call(
                    "GET /texts",
                    "GET",
                    f"/narratives/{fam['narrative']}/texts",
                    params={"status": "pending"},
                )
            ).json()
            for t in texts[:3]:
                await u.call(
                    "POST /texts/validate", "POST", f"/narrative-texts/{t['id']}/validate", json={}
                )
        await asyncio.sleep(random.uniform(0.2, 0.6))


async def check_invariants(families: list[dict], made: dict) -> dict:
    """Vérifie l'état final, famille par famille, avec le compte administrateur."""
    report = {}
    for fam in families:
        admin = fam["users"][0]
        problems = []
        poll = (await admin.call("check", "GET", f"/posts/{fam['poll']}")).json()
        voters = sum(o["votes"] for o in poll["poll"])
        if voters > len(fam["users"]):
            problems.append(f"sondage : {voters} votes pour {len(fam['users'])} membres")
        feed = (await admin.call("check", "GET", "/feed")).json()["items"]
        for post in feed:
            if sum(post["reactions"].values()) > len(fam["users"]):
                problems.append(f"publication {post['id']} : plus de réactions que de membres")
        payments = (
            await admin.call("check", "GET", f"/contributions/events/{fam['event']}/payments")
        ).json()
        refs = Counter(p["reference"] for p in payments)
        doubles = [r for r, n in refs.items() if n > 1]
        if doubles:
            problems.append(f"paiements en double : {doubles[:3]}")
        event = (await admin.call("check", "GET", f"/contributions/events/{fam['event']}")).json()
        validated = sum(p["amount"] for p in payments if p["status"] == "validated")
        if event["totals"]["collected"] != validated:
            problems.append(
                f"total collecté {event['totals']['collected']} ≠ paiements validés {validated}"
            )
        persons = (await admin.call("check", "GET", "/persons", params={"limit": 1000})).json()[
            "items"
        ]
        names = Counter(p["first_name"] for p in persons)
        applied = [m for _, m in made["proposals"][fam["id"]] if names[m] > 1]
        if applied:
            problems.append(f"propositions appliquées deux fois : {applied[:3]}")
        texts = (
            await admin.call(
                "check",
                "GET",
                f"/narratives/{fam['narrative']}/texts",
                params={"status": "validated"},
            )
        ).json()
        layers = Counter(t["layer"] for t in texts)
        if any(n > 1 for n in layers.values()):
            problems.append(f"plusieurs versions de référence pour une couche : {dict(layers)}")
        report[fam["id"]] = {
            "members": len(fam["users"]),
            "persons": len(persons),
            "posts": len(feed),
            "payments": len(payments),
            "validated_total": validated,
            "proposals_made": len(made["proposals"][fam["id"]]),
            "problems": problems,
        }
    return report


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0
    values = sorted(values)
    return round(values[min(len(values) - 1, int(q * len(values)))], 1)


async def main(url: str, n_families: int, members: int, seconds: int, out: str) -> int:
    stats = Stats()
    limits = httpx.Limits(max_connections=400, max_keepalive_connections=200)
    async with httpx.AsyncClient(base_url=url, timeout=60, limits=limits) as client:
        t0 = time.perf_counter()
        families = await asyncio.gather(
            *(setup_family(client, stats, i, members) for i in range(n_families))
        )
        setup_s = time.perf_counter() - t0
        print(
            f"Mise en place : {n_families} familles, {sum(len(f['users']) for f in families)} comptes, {setup_s:.0f} s"
        )
        stats.latency.clear()
        stats.status.clear()
        made = {
            "posts": defaultdict(list),
            "payments": defaultdict(list),
            "proposals": defaultdict(list),
        }
        deadline = time.monotonic() + seconds
        tasks = []
        for fam in families:
            foreign = [f for f in families if f is not fam]
            for u in fam["users"]:
                tasks.append(member_loop(u, fam, deadline, foreign, made))
                if u.role != "member":
                    tasks.append(reviewer_loop(u, fam, deadline, made))
        t1 = time.perf_counter()
        await asyncio.gather(*tasks)
        load_s = time.perf_counter() - t1
        invariants = await check_invariants(families, made)

    total = sum(stats.status.values())
    all_ms = [v for vs in stats.latency.values() for v in vs]
    report = {
        "families": n_families,
        "accounts": sum(len(f["users"]) for f in families),
        "concurrent_loops": len(tasks),
        "seconds": round(load_s, 1),
        "requests": total,
        "throughput_rps": round(total / load_s, 1),
        "status": {str(k): v for k, v in sorted(stats.status.items())},
        "latency_ms": {
            "p50": pct(all_ms, 0.5),
            "p95": pct(all_ms, 0.95),
            "p99": pct(all_ms, 0.99),
            "max": round(max(all_ms), 1),
        },
        "by_action": {
            k: {"n": len(v), "p50": pct(v, 0.5), "p95": pct(v, 0.95), "max": round(max(v), 1)}
            for k, v in sorted(stats.latency.items())
            if k != "check"
        },
        "refusals": {
            f"{a} {s}": n
            for (a, s), n in sorted(stats.by_status.items())
            if s >= 400 and a != "check"
        },
        "server_errors": stats.errors[:20],
        "transport_retries": stats.transport_retries,
        "intrusion_attempts": stats.intrusions,
        "leaks": stats.leaks,
        "invariants": invariants,
    }
    with open(out, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    problems = [p for fam in invariants.values() for p in fam["problems"]]
    print(
        f"Charge : {total} requêtes en {load_s:.0f} s ({report['throughput_rps']} req/s), {len(tasks)} boucles simultanées"
    )
    print(
        f"Latence : médiane {report['latency_ms']['p50']} ms, p95 {report['latency_ms']['p95']} ms, p99 {report['latency_ms']['p99']} ms"
    )
    print(f"Statuts : {report['status']}")
    print(
        f"Erreurs serveur : {len(stats.errors)} ; tentatives d'intrusion : {stats.intrusions}, fuites : {len(stats.leaks)}"
    )
    print(f"Invariants : {'tous respectés' if not problems else problems}")
    for e in stats.errors[:10]:
        print("  ERREUR", e)
    for leak in stats.leaks[:10]:
        print("  FUITE", leak)
    return 0 if not stats.errors and not stats.leaks and not problems else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--url", default="http://localhost:8100")
    parser.add_argument("--families", type=int, default=3)
    parser.add_argument("--members", type=int, default=20)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--out", default="/tmp/sheenu-charge.json")
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(main(args.url, args.families, args.members, args.seconds, args.out))
    )
