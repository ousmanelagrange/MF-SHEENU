# 05 — Guide du code

> Version 1.0 — 27 octobre 2026

Ce guide explique où se trouve chaque chose et comment ajouter une fonctionnalité sans casser la structure. Principe général : **un dossier par domaine métier**, des fichiers courts, une phrase d'explication en tête de chaque fichier, pas d'abstraction tant qu'elle ne sert pas deux fois.

## 1. API (`api/`)

```
app/
├── main.py              assemble les modules, CORS, compression, /health
├── core/                socle technique, sans logique métier
│   ├── config.py        variables d'environnement
│   ├── db.py            connexion, contexte familial pour la RLS
│   ├── deps.py          utilisateur courant, famille courante, rôles
│   ├── security.py      mots de passe, jetons
│   ├── errors.py        erreurs {code, message}
│   └── schemas.py       types communs (Sex, Certainty…)
├── models/              tables SQLAlchemy, un fichier par domaine
├── genealogy/           logique généalogique pure, sans HTTP
│   ├── graph.py         graphe familial : générations, parenté, préséance, périmètre
│   └── kinship.py       nom du lien en français (fonctions pures)
├── shared/              utilitaires communs : audit, stockage des photos
└── modules/             un dossier par domaine métier
    ├── auth/            comptes et jetons
    ├── families/        familles et membres
    ├── invitations/     liens d'invitation
    ├── persons/         fiches (router, schemas, service, presenters)
    ├── relations/       filiations et unions (router, schemas, service)
    ├── tree/            arbre, lien de parenté, statistiques
    ├── titles/          titres et préséance
    ├── proposals/       propositions et validation
    ├── delegations/     fiches confiées à un membre
    ├── data/            GEDCOM, doublons, fusion
    └── audit/           journal
```

### Rôle de chaque fichier d'un module

| Fichier | Contient | Ne contient pas |
|---|---|---|
| `router.py` | Les routes HTTP : lecture de la requête, contrôle des droits et du périmètre, `commit`, réponse | De règle métier complexe |
| `schemas.py` | Les formes des entrées et sorties (Pydantic) | De logique |
| `service.py` | Les règles métier (RG-xx), l'écriture de l'audit | De `commit`, de contrôle du périmètre (l'appelant décide) |
| `presenters.py` | La mise en forme des réponses quand elle est partagée | D'accès à la base |

Cette séparation permet, par exemple, à une proposition acceptée d'appeler exactement le même `persons.service.create_person` que la route directe.

### Ajouter une fonctionnalité à l'API

1. Si une table est nécessaire : un fichier dans `models/`, l'ajouter à `models/__init__.py` (et à `RLS_TABLES` si elle porte `family_id`), puis `alembic revision --autogenerate` et ajouter la politique RLS dans la migration.
2. Créer `modules/<domaine>/` avec `router.py`, `schemas.py`, et `service.py` s'il y a des règles métier.
3. Déclarer le routeur dans `main.py`.
4. Écrire les tests dans `tests/test_<domaine>.py`, avec les aides de `tests/conftest.py` (`Api`, `build_family`, `join_as`).
5. `ruff check app tests && pytest` doivent passer.

## 2. Web (`web/`)

```
src/
├── App.tsx              fournisseurs et table des routes
├── main.tsx             polices, styles, montage
├── theme.ts, styles.css palette ntienya et styles globaux
├── types.ts             types calqués sur l'API
├── lib/                 client HTTP (api.ts) et famille courante (family.tsx)
├── providers/           fournisseurs Refine (données, authentification)
├── components/          briques communes : coquille, marque, personne, partage d'invitation
└── features/            un dossier par fonctionnalité
    ├── auth/  families/  home/  kinship/  titles/  members/  audit/
    ├── tree/            page, dessin SVG, mise en page, export
    ├── persons/         liste, fiche, formulaire, et components/ propres à la fiche
    ├── proposals/       page, compteurs, et useSubmitOrPropose (direct ou proposition)
    └── data/            GEDCOM, doublons
```

**Règles** : une page par fichier ; dès qu'une page dépasse environ 250 lignes, ses blocs vont dans `features/<domaine>/components/`. Les couleurs et polices viennent des variables CSS ou de `theme.ts`, jamais en dur dans une page (sauf le dessin de l'arbre, en attributs pour que l'export reste autonome).

## 3. Mobile (`mobile/`)

```
App.tsx              polices, session, connexion ou navigation
src/navigation.tsx   familles, onglets (Personnes, Arbre, Propositions, Moi), fiche
src/screens/         un fichier par écran
src/components/      briques d'interface et icônes
src/treeLayout.ts    mise en page de l'arbre, identique au web
src/api.ts           client HTTP, jetons conservés sur l'appareil
```

## 4. Conventions communes

- **Langue** : code (noms de variables, fonctions) en anglais ; commentaires, textes d'interface et documentation en français.
- **Commentaires** : une phrase en tête de chaque fichier ; une docstring pour chaque fonction dont le nom ne suffit pas ; les règles métier citent leur code (RG-xx) défini dans [01-analyse.md](01-analyse.md).
- **Simplicité** : pas de couche d'abstraction « au cas où » ; une fonction utilitaire n'est créée qu'à sa deuxième utilisation.
- **Données de famille** : jamais dans le dépôt (il est public). Les secrets vivent dans les variables d'environnement.
- **Commits** : un commit par étape cohérente, message en français décrivant ce qui change pour l'utilisateur.
