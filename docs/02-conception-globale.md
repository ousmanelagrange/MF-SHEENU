# 02 — Conception globale

> Version 1.0 — 27 octobre 2026

## 1. Vue d'ensemble

Sheenu est composée de trois applications clientes et d'une API unique adossée à PostgreSQL. WhatsApp reste en dehors du système : il sert de canal pour partager les liens d'invitation et les récapitulatifs.

```mermaid
flowchart TB
  subgraph Clients
    MOB["📱 Application mobile<br/>React Native · Expo<br/><i>membres</i>"]
    WEB["🖥️ Application web<br/>React · Refine · Vite<br/><i>bureau, chefs de branche, membres</i>"]
  end

  subgraph Serveur["API Sheenu (FastAPI)"]
    AUTH[Auth & comptes]
    FAM[Familles & appartenances]
    GEN[Généalogie<br/>personnes · liens · arbre]
    TIT[Titres & préséance]
    GOV[Propositions & audit]
    COT[Cotisations]
    SOC[Vie sociale]
    MEM[Récits & médias]
    EXP[Exports<br/>GEDCOM · PDF]
  end

  DB[("PostgreSQL<br/>Row Level Security")]
  S3[("Stockage objets<br/>Cloudflare R2 / local")]
  WA["WhatsApp<br/>(hors système)"]

  MOB -- HTTPS / JSON + JWT --> Serveur
  WEB -- HTTPS / JSON + JWT --> Serveur
  Serveur --> DB
  MEM --> S3
  GEN --> S3
  WEB -. partage de liens .-> WA
  MOB -. partage de liens .-> WA
```

## 2. Choix techniques

| Couche | Technologie | Justification |
|---|---|---|
| API | **Python 3.12+, FastAPI** | Léger en mémoire (compatible offres gratuites), typage avec Pydantic, OpenAPI automatique |
| ORM / migrations | **SQLAlchemy 2.0, Alembic** | Mappage typé, migrations versionnées |
| Base de données | **PostgreSQL 16** | Requêtes récursives pour l'arbre, Row Level Security pour l'isolation, JSONB pour l'audit |
| Authentification | **JWT** (accès 30 min + rafraîchissement 30 jours), mots de passe **bcrypt** | Sans état, simple à héberger |
| Web | **React 18, TypeScript, Refine, Ant Design, Vite** | Refine accélère les écrans de gestion (listes, formulaires, droits) |
| Visualisation de l'arbre | **family-chart** (D3) + rendu maison pour l'export | Conçu pour la généalogie, gère conjoints multiples |
| Export image/PDF | **html-to-image + jsPDF** côté client | Aucun coût serveur |
| Mobile | **React Native, Expo, TypeScript** | Même langage que le web, types partagés, Expo Go pour les testeurs |
| Stockage fichiers | **Cloudflare R2** (compatible S3), disque local en développement | Sortie de données gratuite |
| CI | **GitHub Actions** | Gratuit pour les dépôts privés dans la limite des minutes incluses |
| Hébergement | **Render** (API), **Neon** ou **Supabase** (PostgreSQL), **Vercel** ou **Cloudflare Pages** (web) | Offres gratuites |

## 3. Architecture de l'API

L'API suit une architecture en couches, organisée par **module métier**.

```mermaid
flowchart LR
  R["Routeurs<br/>(api/routers)"] --> S["Services<br/>(règles métier)"]
  S --> M["Modèles SQLAlchemy<br/>(models)"]
  M --> DB[(PostgreSQL)]
  R --> SC["Schémas Pydantic<br/>(schemas)"]
  D["Dépendances<br/>auth · famille courante · rôles"] --> R
```

- **Routeurs** : HTTP uniquement (validation d'entrée, codes de retour).
- **Services** : règles métier (RG-xx), transactions, audit.
- **Modèles** : tables et relations.
- **Dépendances** : utilisateur courant, famille courante (en-tête `X-Family-Id`), vérification du rôle.

### Contexte familial

Chaque requête métier porte l'en-tête **`X-Family-Id`**. L'API vérifie que l'utilisateur est membre actif de cette famille, puis positionne la variable de session PostgreSQL `app.family_id` pour que la **Row Level Security** filtre toutes les tables. Une erreur de code applicatif ne peut donc pas faire fuiter les données d'une autre famille.

```mermaid
sequenceDiagram
  participant C as Client
  participant A as API
  participant DB as PostgreSQL
  C->>A: GET /persons (JWT, X-Family-Id: F1)
  A->>A: Vérifie le JWT → user U
  A->>DB: membership(U, F1) actif ?
  DB-->>A: oui, rôle = member
  A->>DB: SET LOCAL app.family_id = 'F1'
  A->>DB: SELECT * FROM person
  Note over DB: RLS : family_id = current_setting('app.family_id')
  DB-->>A: personnes de F1 uniquement
  A-->>C: 200 [ ... ]
```

## 4. Modèle de domaine

```mermaid
classDiagram
  direction LR
  class User {
    id
    email
    phone
    full_name
    locale
  }
  class Family {
    id
    name
    community
    root_person_id
    settings
  }
  class Membership {
    role
    status
    branch_person_id
  }
  class Person {
    id
    first_name
    last_name
    traditional_name
    sex
    birth_date
    death_date
    is_living
    photo_url
    privacy
  }
  class ParentChild {
    kind
    certainty
    source
  }
  class Union {
    kind
    rank
    start_date
    end_date
  }
  class TitleDefinition {
    name
    abbreviation
    precedence
    badge_color
    hereditary
  }
  class TitleHolding {
    conferred_by
    conferred_on
    ended_on
    predecessor_id
  }
  class Invitation {
    token
    expires_at
    used_at
  }
  class Proposal {
    kind
    payload
    status
  }
  class AuditLog {
    action
    entity
    before
    after
  }
  class ContributionRule
  class ContributionEvent
  class Payment
  class Story
  class StoryLayer
  class Post

  User "1" -- "0..2" Membership
  Family "1" -- "*" Membership
  Membership "0..1" -- "0..1" Person : est représenté par
  Family "1" -- "*" Person
  Person "1" -- "*" ParentChild : parent
  Person "1" -- "*" ParentChild : enfant
  Person "1" -- "*" Union : partenaire A
  Person "1" -- "*" Union : partenaire B
  Family "1" -- "*" TitleDefinition
  TitleDefinition "1" -- "*" TitleHolding
  Person "1" -- "*" TitleHolding
  Family "1" -- "*" Invitation
  Family "1" -- "*" Proposal
  Family "1" -- "*" AuditLog
  Family "1" -- "*" ContributionRule
  Family "1" -- "*" ContributionEvent
  ContributionEvent "1" -- "*" Payment
  Family "1" -- "*" Story
  Story "1" -- "*" StoryLayer
  Family "1" -- "*" Post
```

Les entités de cotisation, de récit et de publication figurent ici pour fixer l'architecture ; elles sont implémentées dans les phases 3 à 5.

## 5. Sécurité

| Menace | Contre-mesure |
|---|---|
| Accès aux données d'une autre famille | Vérification d'appartenance + RLS PostgreSQL |
| Vol de mot de passe | bcrypt, politique de longueur minimale, limitation des tentatives |
| Vol de jeton | JWT d'accès court (30 min), jeton de rafraîchissement révocable |
| Invitation détournée | Jeton aléatoire de 32 octets, expiration (7 jours par défaut), usage unique |
| Élévation de privilèges | Contrôle du rôle côté serveur pour chaque action sensible |
| Modification silencieuse | Journal d'audit systématique, suppression logique |
| Injection | ORM paramétré, validation Pydantic |
| Fuite par export | Les exports appliquent les mêmes règles de confidentialité que l'affichage |

### Matrice des rôles (phase 1–2)

| Action | Membre | Chef de branche | Trésorier | Bureau / Admin |
|---|:-:|:-:|:-:|:-:|
| Voir l'arbre et les fiches | ✅ | ✅ | ✅ | ✅ |
| Modifier sa propre fiche | ✅ | ✅ | ✅ | ✅ |
| Proposer un ajout | ✅ | ✅ | ✅ | ✅ |
| Ajouter directement dans sa branche | — | ✅ | — | ✅ |
| Valider une proposition | — | ✅ (sa branche) | — | ✅ |
| Inviter | — | ✅ (sa branche) | — | ✅ |
| Gérer titres, règles, rôles | — | — | — | ✅ |
| Gérer les cotisations | — | — | ✅ | ✅ |

## 6. Flux principaux

### 6.1 Invitation

```mermaid
sequenceDiagram
  actor CB as Chef de branche
  participant W as Web / Mobile
  participant A as API
  actor V as Invité
  CB->>W: Inviter (fiche personne existante ou nouvelle)
  W->>A: POST /invitations
  A-->>W: lien https://app/rejoindre/{token}
  CB->>V: Partage du lien sur WhatsApp
  V->>W: Ouvre le lien
  W->>A: GET /invitations/{token}
  A-->>W: famille, invitant, personne pressentie
  V->>W: Crée son compte ou se connecte
  W->>A: POST /invitations/{token}/accept
  A->>A: Vérifie expiration, usage unique, appartenance existante
  A-->>W: appartenance créée, fiche liée
```

### 6.2 Proposition et validation (phase 2)

```mermaid
stateDiagram-v2
  [*] --> EnAttente : membre propose
  EnAttente --> Acceptée : chef de branche / bureau accepte
  EnAttente --> Refusée : refus avec motif
  EnAttente --> Retirée : l'auteur retire
  Acceptée --> [*] : changement appliqué + audit
  Refusée --> [*]
  Retirée --> [*]
```

### 6.3 Cotisation (phase 3)

```mermaid
sequenceDiagram
  actor T as Trésorier
  actor M as Membre
  participant A as API
  T->>A: Créer l'événement « Deuil de X »
  A->>A: Applique les règles par génération → montant dû par membre
  A-->>T: Liste des montants dus
  T-->>M: Récapitulatif partagé sur WhatsApp
  M->>A: Déclare un paiement + capture du reçu
  T->>A: Valide le paiement
  A-->>M: Statut « payé », tableau mis à jour
```

## 7. Déploiement

```mermaid
flowchart LR
  GH["GitHub<br/>monorepo lignee"] -- push main --> CI["GitHub Actions<br/>tests API · build web"]
  CI -- succès --> RENDER["Render<br/>API FastAPI (Docker)"]
  CI -- succès --> VERCEL["Vercel / Cloudflare Pages<br/>web statique"]
  RENDER --> NEON[("Neon / Supabase<br/>PostgreSQL")]
  RENDER --> R2[("Cloudflare R2<br/>photos, audio")]
  EXPO["Expo Go / EAS<br/>testeurs mobiles"] --> RENDER
```

| Environnement | API | Base | Web |
|---|---|---|---|
| Local | `uvicorn` | PostgreSQL local ou Docker | `vite dev` |
| Test (CI) | pytest | PostgreSQL service GitHub Actions | `vite build` |
| Production | Render (offre gratuite, mise en veille) | Neon ou Supabase (offre gratuite) | Vercel ou Cloudflare Pages |

## 8. Organisation du code

```
lignee/
├── docs/            Analyse, conception, décisions
├── api/             FastAPI
│   ├── app/
│   │   ├── core/    config, sécurité, base de données
│   │   ├── models/  SQLAlchemy
│   │   ├── schemas/ Pydantic
│   │   ├── services/ règles métier (généalogie, parenté, GEDCOM)
│   │   └── routers/ endpoints
│   ├── alembic/     migrations
│   └── tests/
├── web/             React + Refine
├── mobile/          Expo
└── .github/workflows/
```
