"""Crée une famille de démonstration sur 6 générations (titres, polygamie, branches).

Usage : python -m scripts.seed_demo   (depuis le dossier api, base migrée)
Compte créé : demo@lignee.app / demo12345
Les noms sont fictifs.
"""

import random

from fastapi.testclient import TestClient

from app.main import app

EMAIL = "demo@lignee.app"
PASSWORD = "demo12345"

MALE = ["Ibrahim", "Moussa", "Adamou", "Issa", "Oumarou", "Abdou", "Salif", "Mohamadou",
        "Hamidou", "Yaya", "Seidou", "Aboubakar", "Nouhou", "Daouda", "Souleymane", "Idrissou"]
FEMALE = ["Aïssatou", "Mariama", "Fadimatou", "Ramatou", "Hadidja", "Zénabou", "Salamatou",
          "Asmaou", "Habiba", "Maïmouna", "Nafissatou", "Rabiatou", "Kadidja", "Amina", "Safiatou"]
LAST = ["Njoya", "Mfochivé", "Pefoura", "Nchare", "Mbombo", "Njimom", "Mounchili", "Ngouhouo"]
COUNTRIES = ["Cameroun"] * 8 + ["France", "Gabon", "Belgique", "États-Unis", "Allemagne"]
VILLAGES = ["Foumban", "Koutaba", "Foumbot", "Massangam", "Malantouen", "Kouoptamo"]


def main() -> None:
    random.seed(7)
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"login": EMAIL, "password": PASSWORD})
    if r.status_code == 200:
        print("Le compte de démonstration existe déjà.")
        return
    r = c.post(
        "/api/v1/auth/register",
        json={"full_name": "Démo Sheenu", "email": EMAIL, "password": PASSWORD},
    )
    r.raise_for_status()
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    fam = c.post(
        "/api/v1/families",
        headers=h,
        json={
            "name": "Famille Démo",
            "community": "Bamoun",
            "description": "Famille fictive pour tester la plateforme.",
            "my_first_name": "Démo",
            "my_last_name": "Sheenu",
            "my_sex": "M",
        },
    ).json()
    h["X-Family-Id"] = fam["id"]
    me = fam["person_id"]

    def person(first, sex, parents=(), spouse=None, rank=None, year=None, last=None, living=True):
        body = {
            "first_name": first,
            "last_name": last,
            "sex": sex,
            "parent_ids": list(parents),
            "birth_year": year,
            "is_living": living,
            "village": random.choice(VILLAGES),
            "country": random.choice(COUNTRIES) if living else "Cameroun",
        }
        if spouse:
            body["spouse_id"] = spouse
            body["union_rank"] = rank
        r = c.post("/api/v1/persons", headers=h, json=body)
        r.raise_for_status()
        return r.json()["id"]

    titles = {}
    for name, abbr, prec, color, hered in [
        ("Mfon", "Mfon", 1, "#7B1E1E", True),
        ("Pomafon", "Pomafon", 10, "#B8860B", True),
        ("Nji", "Nji", 20, "#2E6B4F", False),
        ("Kom", "Kom", 30, "#3B5B92", False),
    ]:
        titles[name] = c.post(
            "/api/v1/titles",
            headers=h,
            json={"name": name, "abbreviation": abbr, "precedence": prec,
                  "badge_color": color, "hereditary": hered},
        ).json()["id"]

    # Génération 1 : la racine et son époux
    root = person("Ngouo", "F", year=1840, last="Mère fondatrice", living=False)
    king = person("Mbouombouo", "M", spouse=root, year=1835, living=False)
    c.patch("/api/v1/families/current", headers=h, json={"root_person_id": root})

    generation = [(root, king)]
    year = 1865
    heir_line = None
    for g in range(2, 7):
        nxt = []
        for idx, (pa, pb) in enumerate(generation):
            n_children = random.randint(2, 4) if g < 5 else random.randint(1, 3)
            if g == 2:
                n_children = 5
            for k in range(n_children):
                sex = random.choice("MF")
                first = random.choice(MALE if sex == "M" else FEMALE)
                last = random.choice(LAST)
                living = year + 3 * k > 1940
                parents = [p for p in (pa, pb) if p]
                child = person(first, sex, parents, year=year + 3 * k, last=last, living=living)
                if g == 2 and k == 0:
                    heir_line = child
                    c.post(f"/api/v1/persons/{child}/titles", headers=h,
                           json={"title_id": titles["Mfon"], "conferred_by": "Palais royal"})
                elif g == 2:
                    c.post(f"/api/v1/persons/{child}/titles", headers=h,
                           json={"title_id": titles["Pomafon"], "conferred_by": "Palais royal"})
                elif random.random() < 0.08:
                    t = random.choice(["Nji", "Kom"])
                    c.post(f"/api/v1/persons/{child}/titles", headers=h,
                           json={"title_id": titles[t], "conferred_by": "Chefferie de Foumban"})
                # Conjoint(s) : polygamie occasionnelle pour les hommes
                n_spouses = 0 if g == 6 else (2 if sex == "M" and random.random() < 0.2 else 1)
                if n_spouses == 0 or random.random() < 0.15:
                    nxt.append((child, None))
                    continue
                for s in range(n_spouses):
                    ssex = "F" if sex == "M" else "M"
                    spouse = person(random.choice(FEMALE if ssex == "F" else MALE), ssex,
                                    spouse=child, rank=s + 1 if n_spouses > 1 else None,
                                    year=year + 3 * k + 2, last=random.choice(LAST), living=living)
                    nxt.append((child, spouse))
            del idx
        generation = nxt
        year += 28

    # Rattacher le compte de démonstration à la 5e génération de la lignée du Mfon
    tree = c.get("/api/v1/tree", headers=h).json()
    gen5 = [p for p in tree["persons"] if p["generation"] == 5 and p["sex"] == "M"]
    if gen5:
        parent = gen5[0]["id"]
        c.post("/api/v1/relations/parent-child", headers=h,
               json={"parent_id": parent, "child_id": me})
    stats = c.get("/api/v1/stats", headers=h).json()
    print(f"Famille de démonstration créée : {stats['persons']} personnes, "
          f"{stats['generations']} générations (héritier : {heir_line}).")
    print(f"Connexion : {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    main()
