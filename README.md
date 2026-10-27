# MF-SHEENU

Plateforme privée de mémoire et d'organisation des grandes familles africaines : arbre généalogique, liens de parenté, titres et préséance, histoires en langues locales, cotisations.

## Contenu du dépôt

| Dossier | Contenu |
|---|---|
| [`docs/`](docs) | [Analyse](docs/01-analyse.md), [conception globale](docs/02-conception-globale.md), [conception détaillée](docs/03-conception-detaillee.md), [déploiement](docs/04-deploiement.md) |
| [`api/`](api) | API FastAPI + PostgreSQL |
| [`web/`](web) | Application web React + Refine |
| [`mobile/`](mobile) | Application mobile Expo |

## Démarrage local

Prérequis : Python 3.12+, Node 20+, PostgreSQL 16.

```bash
# Base de données (rôle NON superutilisateur, sinon la Row Level Security est ignorée)
createuser lignee -P            # mot de passe : lignee
createdb -O lignee lignee
createdb -O lignee lignee_test

# API
cd api
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
python -m scripts.seed_demo     # famille de démonstration (demo@lignee.app / demo12345)
uvicorn app.main:app --reload   # http://localhost:8000/docs
pytest                           # tests

# Web
cd ../web
npm install
npm run dev                     # http://localhost:5173
```

## Phase en cours

Phase 1 — le cœur : comptes, familles, invitations, personnes, filiations, unions, arbre, calcul de lien, titres, export PNG / PDF / SVG / GEDCOM.
