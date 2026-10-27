# 03 — Conception détaillée (phases 1 à 3)

> Version 1.1 — 27 octobre 2026. Sections 1 à 7 : phase 1 (le cœur). Section 8 : phase 2 (la gouvernance). Section 9 : phase 3 (les cotisations). L'organisation du code est décrite dans [05-guide-du-code.md](05-guide-du-code.md).

## 1. Modèle physique de données

Conventions : clés primaires `uuid` générées par l'application, horodatages `timestamptz` en UTC, noms de tables au singulier en anglais, énumérations stockées en `varchar` contrôlé par l'application (plus simple à faire évoluer que les types `ENUM` PostgreSQL).

```mermaid
erDiagram
  app_user ||--o{ membership : "possède"
  family ||--o{ membership : "regroupe"
  family ||--o{ person : "contient"
  person |o--o| membership : "représente"
  person ||--o{ parent_child : "parent"
  person ||--o{ parent_child : "enfant"
  person ||--o{ family_union : "partenaire A"
  person ||--o{ family_union : "partenaire B"
  family ||--o{ title_definition : "définit"
  title_definition ||--o{ title_holding : "est détenu"
  person ||--o{ title_holding : "détient"
  family ||--o{ invitation : "émet"
  family ||--o{ audit_log : "trace"

  app_user {
    uuid id PK
    varchar email UK
    varchar phone UK
    varchar full_name
    varchar password_hash
    varchar locale
    int token_version
    bool is_active
    timestamptz created_at
  }
  family {
    uuid id PK
    varchar name
    varchar community
    text description
    uuid root_person_id FK
    jsonb settings
    uuid created_by FK
    timestamptz created_at
  }
  membership {
    uuid id PK
    uuid family_id FK
    uuid user_id FK
    uuid person_id FK
    varchar role
    varchar status
    uuid branch_person_id FK
    timestamptz joined_at
  }
  person {
    uuid id PK
    uuid family_id FK
    varchar first_name
    varchar last_name
    varchar traditional_name
    varchar nickname
    varchar sex
    date birth_date
    int birth_year
    varchar birth_place
    date death_date
    int death_year
    varchar death_place
    bool is_living
    varchar village
    varchar country
    text biography
    varchar photo_url
    varchar phone
    varchar email
    varchar contact_visibility
    timestamptz archived_at
    uuid created_by FK
    timestamptz created_at
    timestamptz updated_at
  }
  parent_child {
    uuid id PK
    uuid family_id FK
    uuid parent_id FK
    uuid child_id FK
    varchar kind
    varchar certainty
    text source
  }
  family_union {
    uuid id PK
    uuid family_id FK
    uuid person_a_id FK
    uuid person_b_id FK
    varchar kind
    int rank
    date start_date
    date end_date
    varchar end_reason
    varchar certainty
  }
  title_definition {
    uuid id PK
    uuid family_id FK
    varchar name
    varchar abbreviation
    int precedence
    varchar badge_color
    bool hereditary
    text description
  }
  title_holding {
    uuid id PK
    uuid family_id FK
    uuid title_id FK
    uuid person_id FK
    varchar conferred_by
    date conferred_on
    date ended_on
    uuid predecessor_id FK
    text notes
  }
  invitation {
    uuid id PK
    uuid family_id FK
    varchar token_hash UK
    uuid person_id FK
    varchar role
    uuid created_by FK
    timestamptz expires_at
    timestamptz used_at
    uuid used_by FK
  }
  audit_log {
    uuid id PK
    uuid family_id FK
    uuid user_id FK
    varchar action
    varchar entity
    uuid entity_id
    jsonb before
    jsonb after
    timestamptz created_at
  }
```

### 1.1 Contraintes

| Table | Contrainte | Règle |
|---|---|---|
| `app_user` | `email` unique, `phone` unique, au moins l'un des deux non nul | Identifiant de connexion |
| `membership` | unique (`family_id`, `user_id`) ; unique (`family_id`, `person_id`) | RG-07 |
| `parent_child` | unique (`parent_id`, `child_id`) ; `parent_id <> child_id` | RG-09 (cycle vérifié par le service) |
| `family_union` | `person_a_id <> person_b_id` ; unique (`person_a_id`, `person_b_id`, `kind`) | RG-10 |
| `title_definition` | unique (`family_id`, `name`) | RG-17 |
| `invitation` | `token_hash` unique (SHA-256 du jeton ; le jeton clair n'est jamais stocké) | Sécurité |

### 1.2 Énumérations

| Champ | Valeurs |
|---|---|
| `membership.role` | `member`, `branch_head`, `treasurer`, `secretary`, `admin` |
| `membership.status` | `active`, `suspended` |
| `person.sex` | `M`, `F`, `U` (inconnu) |
| `person.contact_visibility` | `family`, `branch`, `board`, `private` |
| `parent_child.kind` | `biological`, `adoptive`, `recognized` |
| `*.certainty` | `documented`, `oral`, `uncertain` |
| `family_union.kind` | `customary`, `civil`, `religious` |
| `family_union.end_reason` | `divorce`, `death`, `other` |

### 1.3 Index

- `person (family_id, last_name, first_name)` pour la recherche et le tri.
- `parent_child (family_id, parent_id)` et `(family_id, child_id)` pour la remontée et la descente de l'arbre.
- `family_union (family_id, person_a_id)` et `(family_id, person_b_id)`.
- `audit_log (family_id, created_at DESC)`.

### 1.4 Row Level Security

Les tables portant `family_id` et contenant des données généalogiques (`person`, `parent_child`, `family_union`, `title_definition`, `title_holding`, `audit_log`) ont la RLS **activée et forcée** :

```sql
ALTER TABLE person ENABLE ROW LEVEL SECURITY;
ALTER TABLE person FORCE ROW LEVEL SECURITY;
CREATE POLICY family_isolation ON person
  USING (family_id = NULLIF(current_setting('app.family_id', true), '')::uuid)
  WITH CHECK (family_id = NULLIF(current_setting('app.family_id', true), '')::uuid);
```

L'API positionne `app.family_id` avec `set_config(..., true)` au début de **chaque transaction** (écouteur SQLAlchemy `after_begin`), à partir de la famille courante de la requête. Sans famille courante, la variable est vide et ces tables apparaissent vides. Les tables `app_user`, `family`, `membership` et `invitation` sont filtrées par l'application, car elles servent avant que la famille courante soit connue (connexion, liste de mes familles, ouverture d'une invitation).

> Le rôle de connexion de l'API ne doit **pas** être superutilisateur : un superutilisateur ignore la RLS.

## 2. Algorithmes

### 2.1 Ascendants et descendants

Requête récursive bornée par une profondeur maximale (par défaut 20) :

```sql
WITH RECURSIVE anc(id, depth) AS (
  SELECT parent_id, 1 FROM parent_child WHERE child_id = :person_id
  UNION
  SELECT pc.parent_id, anc.depth + 1
  FROM parent_child pc JOIN anc ON pc.child_id = anc.id
  WHERE anc.depth < :max_depth
)
SELECT id, MIN(depth) AS depth FROM anc GROUP BY id;
```

Les descendants utilisent la même requête dans l'autre sens.

### 2.2 Détection de cycle (RG-09)

Avant d'ajouter « P parent de E », le service vérifie que **P n'est pas un descendant de E** (ni E lui-même). Si c'est le cas, la requête est rejetée avec `409 cycle_detected`.

### 2.3 Génération (RG-12)

- La racine est en génération 1.
- Un descendant de la racine a pour génération `1 + longueur du plus court chemin descendant depuis la racine`.
- Un conjoint qui ne descend pas de la racine prend la génération de son conjoint descendant.
- Sans racine définie, la génération est calculée depuis les personnes sans parent connu, la plus ancienne étant 1.

Le calcul se fait en mémoire sur l'arbre chargé (parcours en largeur), ce qui reste instantané jusqu'à plusieurs dizaines de milliers de personnes.

### 2.4 Calcul du lien de parenté (UC4)

1. Calculer les ascendants de A avec leur distance `dA` (A lui-même à 0), idem pour B (`dB`).
2. Les ancêtres communs sont l'intersection ; on retient celui qui minimise `dA + dB` (à égalité, le plus petit `max(dA, dB)`).
3. Le chemin est A → … → ancêtre commun → … → B.
4. Le nom du lien, du point de vue de A (« B est votre … ») :

| dA | dB | Lien (masculin / féminin) |
|---|---|---|
| 0 | 1 | fils / fille |
| 0 | 2 | petit-fils / petite-fille |
| 0 | 3 | arrière-petit-fils / arrière-petite-fille |
| 0 | n ≥ 4 | descendant(e) à la n-ième génération |
| 1 | 0 | père / mère |
| 2 | 0 | grand-père / grand-mère |
| 3 | 0 | arrière-grand-père / arrière-grand-mère |
| n ≥ 4 | 0 | ancêtre à la n-ième génération |
| 1 | 1 | frère / sœur (« demi- » si un seul parent commun) |
| 1 | 2 | neveu / nièce |
| 1 | 3 | petit-neveu / petite-nièce |
| 2 | 1 | oncle / tante |
| 3 | 1 | grand-oncle / grand-tante |
| k | k (k ≥ 2) | cousin(e) germain(e) si k = 2, sinon cousin(e) au (k−1)ᵉ degré |
| autres | | cousin(e) au (min(dA,dB)−1)ᵉ degré, décalé(e) de \|dA−dB\| génération(s) |

5. Sans lien de sang, on teste un niveau d'alliance : B conjoint de A (« époux / épouse »), B conjoint d'un parent de sang de A (« conjoint de votre … »), B parent de sang du conjoint de A (« … de votre conjoint »).
6. Sans aucun lien trouvé : `related = false`.

### 2.5 Préséance (RG-20)

Clé de tri : (rang du titre actif le plus élevé, ou +∞ sans titre) → génération → année de naissance → nom. Le nom affiché est `abréviation du titre + prénom + nom` (exemple : « Nji Ibrahim Mfochivé »).

### 2.6 Périmètre d'écriture

Un utilisateur peut créer ou modifier directement :

| Rôle | Périmètre |
|---|---|
| `admin` | toute la famille |
| `branch_head` | sa personne de branche, ses descendants et leurs conjoints |
| autres rôles | sa propre fiche, ses descendants et leurs conjoints |
| tous | en plus, les personnes qui lui sont **déléguées** et leur descendance (§8.3) |

Hors périmètre, la route directe répond `403 out_of_scope` ; le client propose alors d'envoyer une **proposition** (§8.2).

### 2.7 Export GEDCOM 5.5.1

| Donnée | GEDCOM |
|---|---|
| `person` | `0 @I{n}@ INDI` avec `NAME Prénom /Nom/`, `SEX`, `BIRT/DATE/PLAC`, `DEAT/DATE/PLAC`, `NICK`, `TITL`, `NOTE` |
| `family_union` | `0 @F{n}@ FAM` avec `HUSB`/`WIFE` selon le sexe, `MARR/DATE`, `DIV` si `end_reason = divorce` |
| enfants | `CHIL` dans le `FAM` réunissant les deux parents ; un `FAM` à parent unique est créé si un seul parent est connu |

Les personnes vivantes sont exportées sans coordonnées ; leurs dates de naissance sont exportées seulement si l'utilisateur a demandé l'export complet en tant qu'administrateur.

## 3. API REST

Base : `/api/v1`. Authentification : `Authorization: Bearer <access_token>`. Contexte familial : en-tête `X-Family-Id`. Réponses JSON ; dates au format ISO 8601.

### 3.1 Format des erreurs

```json
{ "detail": { "code": "out_of_scope", "message": "Cette personne est hors de votre périmètre." } }
```

| Code HTTP | Codes métier |
|---|---|
| 400 | `validation_error`, `invalid_invitation` |
| 401 | `not_authenticated`, `invalid_credentials`, `token_expired` |
| 403 | `not_a_member`, `forbidden`, `out_of_scope` |
| 404 | `not_found` |
| 409 | `already_exists`, `cycle_detected`, `too_many_parents` |

### 3.2 Points d'entrée

**Authentification**

| Méthode | Chemin | Description |
|---|---|---|
| POST | `/auth/register` | Créer un compte (`email` ou `phone`, `full_name`, `password`) |
| POST | `/auth/login` | Connexion (`login` = e-mail ou téléphone, `password`) → `access_token`, `refresh_token` |
| POST | `/auth/refresh` | Nouveau jeton d'accès à partir du jeton de rafraîchissement |
| POST | `/auth/logout-all` | Révoque tous les jetons (incrémente `token_version`) |
| GET / PATCH | `/auth/me` | Profil du compte |

**Familles et membres**

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| GET | `/families` | connecté | Mes familles et mon rôle dans chacune |
| POST | `/families` | connecté | Créer une famille ; le créateur devient `admin` et sa fiche personne est créée |
| GET | `/families/current` | membre | Famille courante (`X-Family-Id`) |
| PATCH | `/families/current` | admin | Nom, communauté, description, racine |
| GET | `/members` | membre | Comptes membres et leurs rôles |
| PATCH | `/members/{id}` | admin | Rôle, statut, personne de branche |

**Invitations**

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| POST | `/invitations` | admin, branch_head | Créer ; renvoie le jeton clair **une seule fois** et le lien |
| GET | `/invitations` | admin, branch_head | Invitations de la famille |
| DELETE | `/invitations/{id}` | admin, branch_head | Annuler |
| GET | `/invitations/token/{token}` | public | Aperçu (famille, invitant, personne pressentie) |
| POST | `/invitations/token/{token}/accept` | connecté | Rejoindre la famille |

**Personnes**

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/persons?q=&sort=precedence\|name&skip=&limit=` | Liste paginée `{items, total}` |
| POST | `/persons` | Créer (avec option `parent_ids`, `spouse_id` pour l'attacher immédiatement) |
| GET | `/persons/{id}` | Fiche complète : parents, enfants, conjoints, fratrie, titres, génération |
| PATCH | `/persons/{id}` | Modifier |
| DELETE | `/persons/{id}` | Archiver (RG-16) |
| POST | `/persons/{id}/photo` | Téléverser la photo (JPEG/PNG/WebP, 5 Mo max, redimensionnée à 800 px) |
| GET | `/persons/{id}/ancestors?depth=` | Ascendants avec profondeur |
| GET | `/persons/{id}/descendants?depth=` | Descendants avec profondeur |

**Liens**

| Méthode | Chemin | Description |
|---|---|---|
| POST | `/relations/parent-child` | `parent_id`, `child_id`, `kind`, `certainty`, `source` |
| PATCH / DELETE | `/relations/parent-child/{id}` | Modifier / supprimer |
| POST | `/unions` | `person_a_id`, `person_b_id`, `kind`, `rank`, dates |
| PATCH / DELETE | `/unions/{id}` | Modifier / supprimer |

**Arbre, parenté, exports**

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/tree` | Toutes les personnes visibles (champs publics), filiations, unions, générations, titres |
| GET | `/kinship?from=&to=` | Lien de parenté : `related`, `label`, `common_ancestor_id`, `path`, `distance_from`, `distance_to` |
| GET | `/export/gedcom` | Fichier `.ged` |
| GET | `/stats` | Nombre de personnes, vivants, générations, par pays |

**Titres**

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| GET | `/titles` | membre | Catalogue des titres |
| POST / PATCH / DELETE | `/titles[/{id}]` | admin | Gérer le catalogue |
| POST | `/persons/{id}/titles` | admin | Attribuer un titre |
| PATCH / DELETE | `/title-holdings/{id}` | admin | Modifier / retirer |

**Audit**

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/audit?entity=&skip=&limit=` | admin |

## 4. Application web

| Écran | Route | Contenu |
|---|---|---|
| Connexion / inscription | `/login`, `/register` | E-mail ou téléphone, mot de passe |
| Rejoindre | `/rejoindre/:token` | Aperçu de l'invitation, création de compte ou connexion, acceptation |
| Choix de famille | `/families` | Mes familles ; créer une famille |
| Tableau de bord | `/` | Statistiques, raccourcis |
| Arbre | `/tree` | Arbre interactif centré sur moi, recherche, recentrage, export PNG/PDF, GEDCOM |
| Personnes | `/persons`, `/persons/:id`, `/persons/create`, `/persons/:id/edit` | Liste triée par préséance, fiche, formulaire |
| Lien de parenté | `/kinship` | Choix de deux personnes, chemin et nom du lien |
| Titres | `/titles` | Catalogue (admin) |
| Membres et invitations | `/members`, `/invitations` | Rôles ; génération et copie des liens à partager sur WhatsApp |
| Audit | `/audit` | Journal (admin) |

État d'authentification dans `localStorage` (jetons, famille courante). Un fournisseur de données Refine maison traduit les appels de Refine vers l'API (`{items, total}`, en-tête `X-Family-Id`), et un fournisseur d'authentification gère connexion, rafraîchissement et déconnexion.

## 5. Application mobile

Connexion, choix de la famille, puis quatre onglets : **Personnes** (liste par préséance, recherche), **Arbre** (descendance ou ascendance, profondeur et zoom réglables), **Propositions** (valider ou refuser ; suivre les siennes), **Moi**. La fiche s'ouvre par-dessus les onglets.

## 6. Tests

| Niveau | Outil | Couverture visée |
|---|---|---|
| Unitaires | pytest | Nom du lien, calcul des générations, préséance, GEDCOM |
| Intégration API | pytest + httpx + PostgreSQL réel | Auth, invitations, périmètre d'écriture, cycles, isolation RLS entre deux familles |
| Web | build TypeScript + test manuel guidé | Parcours connexion → arbre → export |
| Bout en bout | navigateur local | Parcours complet sur une famille de démonstration |

Un script `seed_demo.py` crée une famille de démonstration sur 6 générations, avec titres et polygamie, pour les tests manuels.

## 7. Configuration

| Variable | Exemple | Rôle |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://lignee:***@host/lignee` | Connexion PostgreSQL |
| `JWT_SECRET` | 64 caractères aléatoires | Signature des jetons |
| `ACCESS_TOKEN_MINUTES` | `30` | Durée du jeton d'accès |
| `REFRESH_TOKEN_DAYS` | `30` | Durée du jeton de rafraîchissement |
| `CORS_ORIGINS` | `https://lignee.vercel.app` | Origines web autorisées |
| `PUBLIC_WEB_URL` | `https://lignee.vercel.app` | Base des liens d'invitation |
| `STORAGE_BACKEND` | `local` ou `s3` | Stockage des photos |
| `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_PUBLIC_URL` | | Cloudflare R2 |


## 8. Phase 2 — Gouvernance

### 8.1 Nouvelles tables

```mermaid
erDiagram
  family ||--o{ proposal : "reçoit"
  app_user ||--o{ proposal : "propose / valide"
  person ||--o{ delegation : "est confiée"
  membership ||--o{ delegation : "gère"

  proposal {
    uuid id PK
    uuid family_id FK
    uuid author_id FK
    varchar kind
    jsonb payload
    jsonb anchor_ids
    varchar summary
    text message
    varchar status
    uuid reviewer_id FK
    text review_note
    uuid result_id
    timestamptz created_at
    timestamptz reviewed_at
  }
  delegation {
    uuid id PK
    uuid family_id FK
    uuid person_id FK
    uuid membership_id FK
    uuid created_by FK
    timestamptz created_at
  }
```

Les deux tables sont soumises à la même Row Level Security que les autres (migration `0002`).

### 8.2 Propositions (RG-13, RG-14)

| Type (`kind`) | `payload` | Personnes concernées (`anchor_ids`) |
|---|---|---|
| `create_person` | corps de `POST /persons` (avec `parent_ids`, `child_ids`, `spouse_id`) | parents, enfants, conjoint |
| `update_person` | `{person_id, changes}` (champs modifiés seulement) | la personne |
| `archive_person` | `{person_id}` | la personne |
| `add_parent_child` | corps de `POST /relations/parent-child` | parent et enfant |
| `add_union` | corps de `POST /unions` | les deux conjoints |
| `delete_parent_child` | `{link_id}` | parent et enfant du lien |
| `delete_union` | `{union_id}` | les deux conjoints |

**Règles**
- Les données sont validées **à la création** avec le schéma du type ; une phrase lisible (`summary`) est figée à ce moment.
- **Qui valide** : l'administrateur, toujours ; un chef de branche si au moins une personne concernée est dans son périmètre, et jamais sa propre proposition.
- **Accepter** exécute la même fonction de service que la route directe : mêmes contrôles (boucles, deux parents biologiques…), même audit. Si l'opération n'est plus possible, l'erreur est renvoyée et la proposition reste en attente.
- **Refuser** exige un motif, visible par l'auteur. L'auteur peut **retirer** sa proposition tant qu'elle est en attente.

```mermaid
sequenceDiagram
  actor M as Membre
  participant A as API
  actor CB as Chef de branche
  M->>A: POST /persons (hors périmètre)
  A-->>M: 403 out_of_scope
  M->>A: POST /proposals {kind: create_person, payload, message}
  A-->>M: 201 « Ajouter X comme enfant de Y »
  CB->>A: GET /proposals/counts → {to_review: 1}
  CB->>A: POST /proposals/{id}/accept
  A->>A: persons.service.create_person (mêmes contrôles)
  A-->>CB: accepted, result_id
```

### 8.3 Délégation

Le bureau, ou un chef de branche pour sa branche, confie la fiche d'une personne (souvent un ancien sans smartphone) à un membre. Le délégué peut ensuite modifier cette fiche et sa descendance comme s'il s'agissait de la sienne (§2.6).

### 8.4 Import GEDCOM

- Lecture ligne à ligne (`niveau [@réf@] ÉTIQUETTE [valeur]`) ; on retient `NAME`, `SEX`, `BIRT/DATE/PLAC`, `DEAT/DATE/PLAC`, `NICK`, `NOTE` (avec `CONT`/`CONC`), et pour `FAM` : `HUSB`, `WIFE`, `CHIL`, `MARR/DATE`, `DIV`.
- Dates : « 12 MAR 1950 » devient une date ; « ABT 1950 » ou « 1950 », une année seule.
- L'import **ajoute** à l'arbre existant ; il ne fusionne rien automatiquement. Fichier de 10 Mo au plus, réservé à l'administrateur.

### 8.5 Doublons et fusion

**Détection** — deux fiches sont signalées si :
1. prénom et nom identiques, sans tenir compte des accents ni de la casse ;
2. années de naissance à 2 ans près, ou inconnues ;
3. aucune filiation ni union entre elles ;
4. leurs parents ne sont pas **tous différents** quand ils sont connus des deux côtés. Cette règle écarte les homonymes, très fréquents (enfant nommé d'après un aïeul).

**Fusion** de `other` dans `keep` (administrateur) : filiations, unions, titres, délégations et compte éventuel passent sur `keep` (doublons et auto-liens supprimés) ; les champs vides de `keep` sont complétés ; la racine est reportée si besoin ; `other` est archivée. Refusée si l'une est l'ascendante de l'autre, ou si les deux ont un compte.

### 8.6 Nouveaux points d'entrée

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| POST | `/proposals` | membre | Proposer une opération |
| GET | `/proposals?view=review\|mine\|all&status=` | membre | À valider, les miennes, toutes (bureau) |
| GET | `/proposals/counts` | membre | `{to_review, mine_pending}` pour le menu |
| POST | `/proposals/{id}/accept` | valideur | Appliquer |
| POST | `/proposals/{id}/reject` | valideur | Refuser avec motif |
| POST | `/proposals/{id}/withdraw` | auteur | Retirer |
| GET / POST | `/persons/{id}/delegates` | membre / bureau, chef de branche | Délégués d'une fiche |
| DELETE | `/delegations/{id}` | bureau, chef de branche | Retirer une délégation |
| POST | `/import/gedcom` | admin | Importer un fichier `.ged` |
| GET | `/duplicates` | admin | Paires de doublons possibles |
| POST | `/persons/{id}/merge` | admin | Fusionner `{other_id}` dans cette fiche |

`POST /persons` accepte aussi `child_ids` : créer directement un **ascendant** d'enfants existants.

### 8.7 Écrans

| Plateforme | Écran | Contenu |
|---|---|---|
| Web | Formulaires, ajout de proche | Hors périmètre : « Envoyer une proposition », avec message facultatif |
| Web | `/propositions` | À valider (Accepter, Refuser avec motif) ; Mes propositions (statut, motif) ; compteur dans le menu |
| Web | Fiche | « Fiche gérée par » pour confier la fiche d'un ancien |
| Web | `/donnees` | Export et import GEDCOM, doublons avec « Garder celle-ci » |
| Mobile | Onglets | Arbre graphique, propositions à valider avec badge |


## 9. Phase 3 — Cotisations

### 9.1 Tables

```mermaid
erDiagram
  family ||--o{ contribution_scale : "définit"
  family ||--o{ contribution_event : "organise"
  contribution_event ||--o{ contribution_due : "attend"
  contribution_event ||--o{ contribution_payment : "reçoit"
  person ||--o{ contribution_due : "doit"
  person ||--o{ contribution_payment : "paie pour"

  contribution_scale {
    uuid id PK
    varchar name
    varchar currency
    jsonb amounts_by_generation
    int default_amount
    int exempt_under_age
    bool include_spouses
    bool active
  }
  contribution_event {
    uuid id PK
    varchar title
    varchar kind
    varchar currency
    date deadline
    int target_amount
    jsonb scale_snapshot
    varchar status
  }
  contribution_due {
    uuid id PK
    uuid event_id FK
    uuid person_id FK
    int amount
    bool exempt
    varchar note
  }
  contribution_payment {
    uuid id PK
    uuid event_id FK
    uuid person_id FK
    int amount
    varchar method
    varchar reference
    varchar proof_url
    int original_amount
    varchar original_currency
    varchar status
    uuid declared_by FK
    uuid reviewed_by FK
  }
```

Montants entiers dans la devise de l'événement (le franc CFA n'a pas de centimes). RLS sur les quatre tables (migration `0003`).

### 9.2 Calcul des montants dus (RG-23, RG-24)

À la création d'un événement avec barème, pour chaque personne **vivante** de l'arbre :
1. si le barème exclut les conjoints et que la personne est entrée par mariage (aucun parent dans l'arbre, au moins une union, ni racine ni ascendant de la racine) : rien ;
2. si son âge à la date du jour est connu et inférieur à `exempt_under_age` : rien ;
3. sinon : `amounts_by_generation[génération]`, ou `default_amount` si sa génération n'y figure pas ; rien si le montant vaut 0.

Le barème est recopié dans l'événement (`scale_snapshot`) : le modifier ensuite n'a aucun effet sur les collectes ouvertes. Le trésorier peut ajuster ou exempter une personne (avec une note) et en ajouter une. Sans barème, l'événement est une collecte libre, éventuellement avec un objectif.

### 9.3 Paiements (RG-25, RG-26)

```mermaid
stateDiagram-v2
  [*] --> Déclaré : un membre déclare (pour lui ou un proche)
  [*] --> Validé : le trésorier saisit des espèces reçues
  Déclaré --> Validé : le trésorier valide (montant corrigeable)
  Déclaré --> Refusé : refus avec motif
  Validé --> [*]
  Refusé --> [*]
```

- Seuls les paiements **validés** comptent dans « payé ». Statut d'une personne : *exempté*, *à jour* (payé ≥ dû), *partiel*, *non payé*.
- Un membre voit les paiements validés et ses propres déclarations ; les reçus ne sont visibles que du trésorier et de l'auteur.
- **Clôture** : refusée tant qu'un paiement attend ; ensuite plus aucune modification (paiement, ajustement, intitulé).

### 9.4 Points d'entrée

| Méthode | Chemin | Rôle | Description |
|---|---|---|---|
| GET / POST | `/contributions/scales` | membre / trésorier | Barèmes |
| PATCH | `/contributions/scales/{id}` | trésorier | Modifier, activer, désactiver |
| GET / POST | `/contributions/events` | membre / trésorier | Collectes, avec totaux |
| GET / PATCH | `/contributions/events/{id}` | membre / trésorier | Détail, modification |
| POST | `/contributions/events/{id}/close` | trésorier | Clôture définitive |
| GET | `/contributions/events/{id}/dues?status=&q=` | membre | État de chaque personne, par préséance |
| POST | `/contributions/events/{id}/dues` | trésorier | Ajouter une personne |
| PATCH | `/contributions/dues/{id}` | trésorier | Ajuster, exempter, noter |
| GET / POST | `/contributions/events/{id}/payments` | membre | Paiements ; déclarer |
| POST | `/contributions/payments/{id}/proof` | auteur, trésorier | Joindre le reçu |
| POST | `/contributions/payments/{id}/validate` \| `reject` | trésorier | Valider (montant corrigeable) ou refuser avec motif |
| GET | `/contributions/events/{id}/recap?only_unpaid=` | membre | Texte pour WhatsApp |
| GET | `/contributions/events/{id}/export.csv` | membre | Export pour Excel (`;`, UTF-8 avec BOM) |
| GET | `/contributions/persons/{id}` | membre | Historique d'une personne |

Le trésorier (`treasurer`) et l'administrateur gèrent ; tout membre consulte et déclare.

### 9.5 Écrans

| Plateforme | Écran | Contenu |
|---|---|---|
| Web | `/cotisations` | Collectes en cours et clôturées, avancement, création |
| Web | `/cotisations/:id` | Avancement, état par personne (recherche, filtres), paiements (validation), déclaration, récapitulatif WhatsApp, export, clôture |
| Web | `/cotisations/baremes` | Barèmes : montant par génération, exemption d'âge, conjoints |
| Web | Accueil, fiche | Mes cotisations en cours ; historique de la personne |
| Mobile | Onglet Cotisations | Collectes, ma part, déclarer, valider (trésorier), état de chacun |
