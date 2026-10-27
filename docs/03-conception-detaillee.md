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

### 9.6 Réunir deux familles

Deux familles créées séparément (une micro-famille et la grande famille, deux branches qui se découvrent) peuvent n'en faire plus qu'une. Le choix retenu est une **absorption validée des deux côtés**, sans lien permanent entre familles, pour garder l'isolement strict (RLS) :

1. l'administrateur de la famille **d'accueil** crée une demande (`POST /family-merges`) et obtient un lien à usage unique, valable 7 jours par défaut, avec un texte prêt à envoyer par WhatsApp ;
2. l'administrateur de la famille **source** ouvre le lien (`GET /family-merges/token/{t}`) : il voit la famille qui l'accueillerait et qui le propose ;
3. depuis sa famille, il confirme (`POST /family-merges/token/{t}/accept`). L'opération est définitive.

Dans une seule transaction, l'arbre source est copié dans la famille d'accueil (personnes, filiations, unions, titres regroupés par nom, délégations) ; un inscrit présent des deux côtés garde une seule fiche. Les autres personnes communes se rapprochent ensuite avec l'outil de doublons (§8.5). Les inscrits rejoignent la famille d'accueil : un administrateur source devient chef de sa branche, trésorier et secrétaire redeviennent membres. La famille source est marquée `merged_into_id` : elle disparaît des listes et toute requête sur elle répond `410 family_merged`. Collectes, propositions et journal restent attachés à la source comme archive.

| Écran | Contenu |
|---|---|
| Web `/donnees` | « Réunir une autre famille à la nôtre » : créer le lien |
| Web `/reunir/:token` | Aperçu, choix de la famille source, confirmation |

## 10. Phase 4 — Vie sociale

### 10.1 Tables (migration 0005, toutes sous RLS)

| Table | Rôle |
|---|---|
| `post` | Publication : `kind` (post, announcement, life_event, poll), `life_event`, texte, photos (`media`), personnes citées, `on_behalf_of` (publié pour un ancien délégué), `pinned`, `hidden` |
| `poll_option`, `poll_vote` | Choix d'un sondage ; un vote par membre, modifiable |
| `comment` | Commentaire d'une publication |
| `reaction` | Une réaction par membre et par publication (like, love, pray, clap) |
| `story` | Photo visible 24 h (`expires_at`) |
| `report` | Signalement d'une publication ou d'un commentaire, avec motif et décision |
| `memorial_message` | Hommage déposé sur la fiche d'une personne décédée |

### 10.2 Règles

- Seuls l'administrateur et le secrétaire (la « modération ») publient des **annonces officielles** ; une annonce est épinglée d'office et s'affiche en tête du fil.
- Une **annonce de vie** peut être publiée au nom d'une personne confiée (délégation, RG-15).
- Un membre ne voit pas les contenus masqués ; la modération les voit, signalés comme tels.
- Une story expire au bout de 24 heures ; elle n'est plus listée ensuite.
- Le mémorial n'existe que pour une personne décédée. L'auteur ou la modération retire un hommage.
- Les anniversaires listent les personnes vivantes dont la date complète est connue, sur les N prochains jours.

### 10.3 Points d'entrée

| Méthode | Chemin | Accès | Rôle |
|---|---|---|---|
| GET | `/feed?before=&kind=` | membre | Fil paginé (20), épinglées d'abord |
| POST | `/posts` | membre (annonce : modération) | Publier |
| GET / PATCH / DELETE | `/posts/{id}` | membre ; auteur ou modération | Lire, corriger, épingler, masquer, supprimer |
| PUT / DELETE | `/posts/{id}/reaction` | membre | Réagir, retirer sa réaction |
| POST | `/posts/{id}/vote` | membre | Voter |
| GET / POST | `/posts/{id}/comments` | membre | Commentaires |
| DELETE | `/comments/{id}` | auteur, modération | Supprimer |
| GET / POST / DELETE | `/stories` | membre | Stories du jour |
| POST / GET | `/reports` | membre ; modération | Signaler ; liste en attente |
| POST | `/reports/{id}/resolve?hide=` | modération | Masquer ou classer |
| GET / POST | `/persons/{id}/memorial` | membre | Hommages |
| DELETE | `/memorial/{id}` | auteur, modération | Retirer |
| GET | `/birthdays?days=` | membre | Anniversaires à venir |

### 10.4 Écrans

| Plateforme | Écran | Contenu |
|---|---|---|
| Web | `/fil` | Stories, rédaction (publication, annonce de vie, sondage, annonce officielle, photo, identification), filtres, publications, anniversaires |
| Web | `/moderation` | Signalements en attente : masquer ou classer |
| Web | Fiche d'un défunt | Mémorial |
| Web | Accueil | Anniversaires à venir |
| Mobile | Onglet Fil | Stories, publication rapide (texte), réactions, votes |
| Mobile | Publication | Publication ouverte et commentaires |
| Mobile | Moi → Propositions | Les propositions quittent la barre d'onglets au profit du Fil ; le badge reste sur « Moi » |

## 11. Phase 5 — Mémoire

Objectif : conserver les histoires racontées par les anciens dans leur langue, avec une transcription et des traductions fidèles (RG relatives aux récits), et rassembler les photos de famille.

### 11.1 Tables (migration 0006, toutes sous RLS)

| Table | Rôle |
|---|---|
| `narrative` | Récit : titre, langue du conteur, conteur (`teller_id`, souvent un ancien sans compte), auteur de l'enregistrement, média (`media_url`, `media_kind` audio ou vidéo), époque (`era` libre, `year` pour la frise), lieu, personnes citées |
| `narrative_text` | Une version d'une **couche** : `original` (transcription), `fr`, `en`. Statut `pending`, `validated`, `superseded`, `rejected`, avec relecteur, date et motif |
| `album` | Album photo : titre, description, année |
| `album_photo` | Photo d'un album : adresse, légende, année, personnes reconnues (`person_ids`) |

### 11.2 Couches de texte et relecture

La fidélité d'un récit compte plus que sa vitesse de publication. Chaque couche n'a qu'une **version de référence** à la fois, et chaque changement garde la trace du précédent :

1. tout membre propose une version d'une couche (première transcription, traduction, correction) ;
2. un **gardien de la mémoire** (administrateur, secrétaire, chef de branche) la relit ; l'écran de relecture montre les ajouts et retraits mot à mot par rapport au texte actuel ;
3. une fois validée, elle devient la référence ; l'ancienne passe en `superseded` et reste consultable ; un refus porte un motif visible par l'auteur ;
4. la proposition d'un gardien est validée d'office, comme pour les propositions de la phase 2.

La transcription automatique n'est pas branchée : aucun service gratuit ne reconnaît le shüpamom de façon fiable. Le modèle accepte toutefois qu'une transcription automatique arrive plus tard comme une proposition parmi d'autres, soumise à la même relecture.

### 11.3 Médias

`POST /uploads/media` reçoit un fichier audio ou vidéo (mp3, m4a, aac, ogg, webm, wav, mp4, mov), 30 Mo au plus, rangé tel quel dans le dossier de la famille (disque local ou Cloudflare R2). Sur le web, le micro du navigateur enregistre directement (MediaRecorder). Les images restent redimensionnées et converties en WebP par `POST /uploads/image`.

### 11.4 Points d'entrée

| Méthode | Chemin | Accès | Rôle |
|---|---|---|---|
| GET | `/narratives?person_id=&q=&to_review=` | membre | Récits ; ceux d'une personne (citée ou conteuse) ; ceux qui ont des textes à relire |
| POST | `/narratives` | membre | Créer, avec un premier texte facultatif |
| GET / PATCH / DELETE | `/narratives/{id}` | membre ; auteur ou gardien | Lire, modifier, supprimer |
| GET | `/narratives/{id}/texts?layer=&status=` | membre | Historique des versions |
| POST | `/narratives/{id}/texts` | membre | Proposer une version d'une couche |
| POST | `/narrative-texts/{id}/validate` \| `reject` | gardien | Relecture, motif facultatif |
| GET / POST | `/albums` | membre | Albums ; créer |
| GET / PATCH / DELETE | `/albums/{id}` | membre ; auteur ou gardien | Album et ses photos |
| POST | `/albums/{id}/photos` | membre | Ajouter une photo |
| PATCH | `/album-photos/{id}` | membre (personnes) ; auteur ou gardien (légende, année) | Reconnaître des personnes, légender |
| DELETE | `/album-photos/{id}` | auteur, gardien | Retirer |
| GET | `/persons/{id}/photos` | membre | Photos où la personne est reconnue |
| GET | `/timeline?person_id=` | membre | Frise : naissances, unions, décès, récits, albums ou photos, annonces de vie |
| POST | `/uploads/media` | membre | Envoi audio ou vidéo |

### 11.5 Écrans

| Plateforme | Écran | Contenu |
|---|---|---|
| Web | `/memoire` | Récits : recherche, filtre « à relire », nouveau récit avec enregistrement au micro ou fichier |
| Web | `/memoire/recits/:id` | Lecteur, édition bilingue (deux couches côte à côte, au choix), proposer, relire avec comparaison |
| Web | `/memoire/albums`, `/memoire/albums/:id` | Albums, ajout de plusieurs photos, visionneuse, reconnaissance des personnes |
| Web | `/memoire/frise` | Frise par décennie, filtres, autour d'une personne |
| Web | Fiche d'une personne | Récits qui la concernent, photos où elle apparaît, lien vers sa frise |
| Mobile | Plus → Mémoire | Récits, albums, frise |
| Mobile | Récit | Lecteur audio, couches au choix, proposer une correction ou une traduction |
| Mobile | Album | Grille, visionneuse, ajout de photos depuis la galerie |
| Mobile | Fil | Publication avec photo depuis la galerie |

## 12. Phase 6 — Intégrations

Objectif : que la plateforme travaille avec WhatsApp au lieu de le remplacer, sans rien payer tant que la famille ne le décide pas, et qu'elle reste utilisable avec un réseau faible (ENF-04).

### 12.1 Tables (migration 0007)

| Table | RLS | Rôle |
|---|---|---|
| `notification` | oui | Message pour un membre dans une famille : type, titre, extrait, lien, lu ou non |
| `join_request` | oui | Demande de rattachement : identité, « comment je me rattache », village, pays, téléphone, statut, fiche attribuée, motif |
| `join_link` | non | Lien de rattachement de la famille (empreinte du jeton). Lu avant de connaître la famille, comme une invitation |
| `payment_intent` | non | Paiement lancé chez un prestataire. Lu par le webhook, qui arrive sans famille, avant d'ouvrir le contexte RLS |

### 12.2 Notifications

Créées dans la même transaction que l'action (`app/shared/notify.py`) ; l'auteur de l'action n'est jamais notifié.

| Événement | Destinataires |
|---|---|
| Annonce du bureau, annonce de vie | Tous les membres |
| Commentaire | Auteur de la publication |
| Proposition acceptée ou refusée | Auteur, avec le motif |
| Paiement validé ou refusé (trésorier ou prestataire) | Déclarant |
| Texte de récit validé ou refusé | Auteur |
| Demande de rattachement reçue | Administrateurs et chefs de branche |
| Rattachement accepté | Nouveau membre |

Web : cloche avec compteur, relue chaque minute. Mobile : compteur sur l'onglet « Plus » et écran Notifications.

### 12.3 Rattachement (RG-04)

1. L'administrateur crée le **lien de rattachement** et le poste dans le groupe WhatsApp. Le jeton n'est montré qu'une fois ; en créer un nouveau invalide l'ancien.
2. Le visiteur crée son compte, ne voit que le nom de la famille, et décrit comment il s'y rattache.
3. Un administrateur ou un chef de branche le place : **comme enfant** d'une personne de l'arbre (filiation créée, certitude « orale »), **sur une fiche existante** sans compte, ou **sur une nouvelle fiche**. Un chef de branche ne place que dans sa branche ; seul l'administrateur nomme un chef de branche.
4. Un refus porte un motif ; le visiteur peut compléter et renvoyer sa demande.

### 12.4 Messagerie (`app/integrations/messaging.py`)

Interface `Messenger.send(numéro, texte)`. Deux implémentations : `ShareMessenger` (par défaut) renvoie un lien `wa.me` à ouvrir ; `WhatsAppCloudMessenger` envoie par l'API WhatsApp Business et garde le lien en secours. Les numéros sont normalisés au format international (un numéro à 9 chiffres est supposé camerounais).

- **Rappels de cotisation** (trésorier) : un message par personne en retard, avec sa part, ce qui est versé et ce qui reste. Le numéro est celui de la fiche, sinon du compte, sinon du délégué qui gère la fiche.
- **Résumé de la semaine** : nouvelles personnes, annonces, collectes en cours, nouveaux récits, anniversaires. Il est écrit avec le gras WhatsApp, prêt à coller dans le groupe.

### 12.5 Paiement Mobile Money (`app/integrations/payments.py`)

Interface `PaymentGateway` : `start()` ouvre la transaction chez le prestataire et `parse_webhook()` vérifie la signature et lit le résultat. Le paiement est créé « déclaré » ; le webhook signé (HMAC-SHA256) le passe en « validé » ou « refusé » et prévient le payeur. Un second appel du webhook est sans effet. Seul le simulateur est livré : aucun prestataire réel n'a été branché sans son contrat ni sa documentation.

### 12.6 Diaspora

`GET /diaspora` compte les personnes vivantes par pays de résidence, en regroupant les écritures (« france », « France »). Le web place un cercle par pays sur une carte Equal Earth (frontières Natural Earth 1:110m, chargées à la demande). Les noms de pays saisis en français sont reliés au code ISO de la carte ; un pays inconnu de cette table reste dans le classement. `GET /persons?country=` liste les personnes d'un pays.

### 12.7 Mobile hors connexion

Les réponses des écrans de lecture (familles, personnes, arbre, fil, récits, albums, frise, collectes, diaspora, notifications) sont gardées sur le téléphone, par famille. `offline.ts` les précharge à l'ouverture d'une famille ; sans réseau, la recherche de personnes et les fiches sont reconstituées à partir de l'arbre.

Les actions passent par `sync.ts` : si le réseau manque, elles entrent dans une file d'envoi (AsyncStorage `sheenu.outbox`) avec une clé `Idempotency-Key`. La file repart dans l'ordre au retour du réseau ; une réponse 4xx marque l'envoi en échec (visible dans **Envois en attente**), une absence de réseau, un 5xx, un 409 `in_progress` ou un 429 le laissent en file. Détail et vérifications : [07 — Tests et sécurité](07-tests-et-securite.md) §5.

### 12.8 Points d'entrée

| Méthode | Chemin | Accès | Rôle |
|---|---|---|---|
| GET | `/notifications` | membre | Les 40 dernières et le nombre de non lues |
| POST | `/notifications/read` | membre | Marquer comme lues (toutes ou une liste) |
| GET / POST / DELETE | `/join-link` | admin (lecture : chef de branche) | État, création ou remplacement, désactivation |
| GET / POST | `/join/{token}` | compte connecté | Aperçu (nom de la famille seulement) ; envoyer sa demande |
| GET | `/join-requests?status=` | admin, chef de branche | Demandes |
| POST | `/join-requests/{id}/accept` \| `reject` | admin, chef de branche | Placer dans l'arbre ; refuser avec motif |
| GET | `/digest?days=` | membre | Résumé et lien de partage WhatsApp |
| GET | `/diaspora` | membre | Pays de résidence |
| POST | `/contributions/events/{id}/reminders` | trésorier | Rappels personnalisés |
| GET | `/contributions/online` | membre | Paiement en ligne activé ? |
| POST | `/contributions/events/{id}/pay-online` | membre | Lancer un paiement Mobile Money |
| POST | `/webhooks/payments/{provider}` | prestataire (signature) | Confirmation |

### 12.9 Écrans

| Plateforme | Écran | Contenu |
|---|---|---|
| Web | Barre latérale | Cloche des notifications |
| Web | Accueil | Résumé de la semaine, partager sur WhatsApp ou copier |
| Web | Membres et invitations | Demandes de rattachement, lien de rattachement |
| Web | `/rattachement/:token` | Page du visiteur : compte, demande, suivi |
| Web | Collecte | « Relancer » (trésorier), « Payer par Mobile Money » (si activé) |
| Web | `/diaspora` | Carte, classement des pays, personnes du pays choisi |
| Mobile | Plus | Notifications, la famille dans le monde ; compteur combiné sur l'onglet |
| Mobile | Partout | Lecture hors connexion avec bandeau |

## 13. Sécurité, robustesse et supervision

Mesures, tests et résultats chiffrés : [07 — Tests et sécurité](07-tests-et-securite.md). Ici, l'organisation du code.

### 13.1 Couche `app/security/`

| Fichier | Rôle |
|---|---|
| `events.py` | `record()` : écrit un événement dans `security_event`, dans sa propre transaction (`AuxSession`), même si la requête échoue |
| `ratelimit.py` | Fenêtres glissantes en mémoire par clé (adresse, compte) ; désactivable par `RATE_LIMIT=false` |
| `middleware.py` | Middlewares ASGI, de l'extérieur vers l'intérieur : en-têtes de sécurité, métriques et numéro de requête (`request_metric` par minute, limite globale par adresse), taille des corps, compression, signature des médias, idempotence |
| `media.py` | Liens de médias signés HMAC (6 h) ou présignés S3 ; `own_media()` refuse les adresses externes et les médias d'une autre famille |

### 13.2 Sessions

`auth_session` : une ligne par appareil, avec l'empreinte du jeton de rafraîchissement courant. À chaque rafraîchissement le jeton change ; un ancien jeton présenté de nouveau ferme toutes les sessions et incrémente `token_version` (les jetons d'accès en cours deviennent invalides). Une tolérance de 30 secondes couvre deux rafraîchissements simultanés du même appareil.

### 13.3 Concurrence

- Réactions et votes : `INSERT ... ON CONFLICT DO UPDATE` sur `uq_reaction` et `uq_poll_vote`.
- Validation d'une proposition, d'un paiement, d'un texte de récit, d'une demande de rattachement : `SELECT ... FOR UPDATE` puis contrôle de l'état ; le second validateur reçoit 400.
- `idempotency_key` : la première requête réserve la clé (`in_progress`), la réponse est stockée ; un rejeu reçoit la même réponse, un rejeu pendant le traitement reçoit 409.

### 13.4 Base de données

- Migration 0008 : tables de plateforme et déclencheurs d'ajout seul sur `audit_log`, `platform_audit`, `security_event`.
- Migration 0009 : `family.graph_version`, incrémenté par des déclencheurs sur `person`, `parent_child`, `family_union`, `title_definition`, `title_holding`, `membership`, `delegation`.
- `app/core/db.py` : pool principal (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) et pool auxiliaire `aux_engine` pour les tables de plateforme (`DB_AUX_POOL_SIZE`) ; `statement_timeout` 30 s et `idle_in_transaction_session_timeout` 60 s par connexion (`DB_SESSION_GUARDS`).

### 13.5 Cache de l'arbre

`load_graph(ctx)` (`app/genealogy/graph.py`) garde par processus les 16 derniers graphes, indexés par famille, avec `graph_version` et la racine. Le graphe est chargé dans une session séparée : si sa version diffère de celle que voit la requête (modification de l'arbre non encore validée dans la transaction en cours), il est rechargé dans la transaction et n'est pas mis en cache.

### 13.6 Supervision

`user.is_platform_admin`, attribué uniquement par `python -m app.cli operator add`. Dépendance `Operator` (`app/core/deps.py`) sur toutes les routes `/platform/*`. Les nombres par famille sont calculés famille par famille dans leur contexte RLS ; aucun contenu n'est renvoyé. Chaque consultation et action est inscrite dans `platform_audit`.

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/platform/overview` | Santé, comptes, familles, trafic résumé |
| GET | `/platform/traffic?hours=` | Requêtes, erreurs et latence par tranche |
| GET | `/platform/events?severity=&kind=` | Journal de sécurité |
| GET | `/platform/users?q=` | Comptes (identité, état, dernière connexion, sessions) |
| GET | `/platform/families` | Familles en nombres |
| GET | `/platform/audit` | Journal de l'opérateur |
| POST | `/platform/users/{id}/disable` \| `enable` \| `unlock` \| `revoke-sessions` | Action sur un compte, motif obligatoire |
| POST | `/platform/maintenance/purge` | Efface les clés d'idempotence de plus de 48 h et les compteurs de plus de 90 jours |

Routes de compte ajoutées : `POST /auth/password`, `GET /auth/sessions`, `DELETE /auth/sessions/{id}`, `POST /auth/logout`, `POST /auth/logout-all`.

### 13.7 Écrans

| Plateforme | Écran | Contenu |
|---|---|---|
| Web | `/compte` | Mot de passe, appareils connectés, déconnexion de partout, accès à la supervision |
| Web | `/supervision` | Vue d'ensemble, Sécurité, Comptes, Familles, Journal de l'opérateur |
| Web, mobile | Partout | Bandeau hors connexion (nombre d'envois en attente sur mobile) |
| Mobile | Plus → Envois en attente | File d'envoi : envoyer maintenant, relancer, abandonner |
