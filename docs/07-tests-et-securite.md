# 07 — Tests, charge et sécurité

> Version 1.0 — 27 octobre 2026

Ce document décrit comment Sheenu est vérifié : les tests automatiques, l'essai de charge à plusieurs utilisateurs simultanés, les mesures de sécurité et la supervision de la plateforme. Il se lit avec [03 — Conception détaillée](03-conception-detaillee.md) §13 (détail technique) et [04 — Déploiement](04-deploiement.md) (réglages de production).

## 1. Lancer les vérifications

```bash
cd api && . .venv/bin/activate
pytest                          # 107 tests, dont 18 de sécurité (tests/test_security.py)
ruff check app tests
bandit -q -r app -ll            # analyse statique Python
pip-audit -r requirements.txt   # dépendances Python connues vulnérables
cd ../web && npm audit --omit=dev
cd ../mobile && npm audit --omit=dev
```

La CI (GitHub Actions) exécute les tests, le lint, le build web et le typage mobile à chaque `push`.

## 2. Tests de sécurité (`api/tests/test_security.py`)

| Test | Ce qui est vérifié |
|---|---|
| Fouille de toutes les routes | Chaque route de l'OpenAPI est appelée par un membre de la famille B avec les identifiants de la famille A (chemin, requête, corps). Aucune réponse 2xx ne doit contenir un identifiant de A ni un secret. |
| Écritures croisées | Des corps valides visant A depuis B sont refusés et rien n'est écrit. |
| RLS en SQL brut | Une requête SQL sans filtre, dans le contexte de B, ne voit aucune ligne de A. |
| Verrouillage | 5 mots de passe faux bloquent le compte 15 minutes, puis la durée double (jusqu'à 4 h). |
| Débit par adresse | Au-delà du seuil, l'API répond 429 avec `Retry-After`. |
| Temps constant | Un compte inexistant prend le même temps qu'un mauvais mot de passe (pas de détection des comptes). |
| Rejeu du jeton de rafraîchissement | Réutiliser un ancien jeton ferme toutes les sessions du compte. |
| Mots de passe | Mots de passe courants ou contenant le nom refusés ; le changement ferme les autres appareils. |
| Jetons forgés | Signature, algorithme `none`, jeton expiré ou d'une ancienne version : 401. |
| Médias | Lien signé et limité dans le temps ; un média d'une autre famille ou une adresse externe sont refusés. |
| En-têtes et tailles | En-têtes de sécurité présents ; corps trop gros refusé (413). |
| Idempotence | Une requête rejouée avec la même `Idempotency-Key` ne crée qu'un seul enregistrement. |
| Journaux | `audit_log`, `platform_audit` et `security_event` refusent toute modification et suppression. |
| Supervision | Réservée aux opérateurs ; ne renvoie aucun contenu de famille. |
| Erreurs imprévues | Réponse 500 générique avec numéro de requête, sans trace. |

## 3. Essai de charge à plusieurs utilisateurs

Le simulateur `api/tests/load/simulate.py` joue de vrais usages en parallèle contre une API lancée à part (4 processus) et une base dédiée.

```bash
createdb -O lignee lignee_load
DATABASE_URL=postgresql+psycopg://lignee:lignee@localhost/lignee_load alembic upgrade head
DATABASE_URL=...lignee_load RATE_LIMIT=false DB_POOL_SIZE=5 DB_MAX_OVERFLOW=5 DB_AUX_POOL_SIZE=2 \
  uvicorn app.main:app --port 8100 --workers 4
python -m tests.load.simulate --families 3 --members 20 --seconds 60
```

`RATE_LIMIT=false` est indispensable : sinon les 60 comptes, qui viennent tous de la même adresse, seraient freinés par la limite par adresse.

**Mise en place** : 3 familles de 20 comptes (administrateur, trésorier, chefs de branche, membres), un arbre d'environ 40 personnes par famille, une collecte, un sondage, un récit.

**Pendant 60 secondes, 72 boucles simultanées** :

- les membres lisent le fil, l'arbre, les personnes, les récits, les notifications ; publient, commentent, réagissent, votent, proposent des modifications, déclarent des paiements ;
- les responsables valident en même temps les mêmes propositions, paiements et textes (courses voulues) ;
- doubles appuis volontaires sur les réactions et les votes ; paiements rejoués avec la même clé d'idempotence ;
- chaque compte tente régulièrement de lire ou d'écrire dans une autre famille.

**À la fin, le simulateur contrôle les invariants** dans chaque famille : une réaction et un vote au plus par personne et par publication, chaque paiement validé une seule fois, total validé égal à la somme des paiements validés, aucune proposition appliquée deux fois, aucune donnée d'une famille visible depuis une autre.

### Résultat du 27 octobre 2026

Machine d'essai : 2 processeurs partagés entre PostgreSQL, les 4 processus de l'API et le simulateur.

| Mesure | Valeur |
|---|---|
| Requêtes | 3 804 en 62 s (61 req/s) |
| Latence | médiane 798 ms, p95 2,8 s, p99 4,1 s |
| Erreurs serveur (5xx) | **0** |
| Tentatives d'intrusion | 200, toutes refusées (100 × 403, 100 × 404), **0 fuite** |
| Refus attendus | 40 validations de paiement déjà faites, 37 validations de texte déjà faites, 24 paiements rejoués pendant leur traitement (409) |
| Invariants | **tous respectés** |

Les latences mesurent surtout la saturation du processeur de la machine d'essai. Sans charge, sur la famille de démonstration (535 personnes) : `/persons` 13 ms, `/feed` 27 ms, `/tree` 37 ms.

### Défauts trouvés et corrigés par cet essai

| Défaut | Correction |
|---|---|
| Deux réactions ou votes simultanés du même compte : violation de contrainte (500) | `INSERT ... ON CONFLICT DO UPDATE` |
| Deux responsables valident le même paiement, la même proposition ou le même texte | Verrou de ligne `FOR UPDATE`, le second reçoit 400 « déjà traité » |
| Pool de connexions épuisé : écritures du journal de sécurité dans une connexion imbriquée, appels bloquants dans la boucle asynchrone | Pool séparé pour les tables de plateforme ; idempotence exécutée hors de la boucle |
| Transactions orphelines après l'arrêt brutal d'un processus | `statement_timeout` 30 s et `idle_in_transaction_session_timeout` 60 s par connexion |
| Arbre recalculé à chaque requête | Cache par processus, invalidé par un numéro de version que des déclencheurs incrémentent à chaque modification de l'arbre |

### Dimensionner le pool de connexions

Chaque processus ouvre au plus `DB_POOL_SIZE + DB_MAX_OVERFLOW + DB_AUX_POOL_SIZE + 5` connexions. Règle : **nombre de processus × ce total < connexions autorisées par la base − 10**. Exemple Neon gratuit (environ 100 connexions) avec un seul processus sur Render : les valeurs par défaut (10 + 20 + 3 + 5 = 38) conviennent.

## 4. Mesures de sécurité

**Isolement des familles.** Chaque requête fixe `app.family_id` dans la transaction ; la Row Level Security de PostgreSQL filtre toutes les tables de famille. Le rôle de l'application n'est ni superutilisateur ni `BYPASSRLS` (`/health` renvoie `rls_enforced`). Une tentative d'accès à une autre famille est inscrite au journal de sécurité.

**Comptes et sessions.**

- Mots de passe bcrypt ; mots de passe courants ou contenant le nom refusés.
- Verrouillage progressif après 5 échecs ; temps de réponse identique que le compte existe ou non.
- Une session par appareil ; jeton de rafraîchissement à usage unique ; un ancien jeton rejoué ferme toutes les sessions du compte.
- Changement de mot de passe, liste des appareils, déconnexion de partout (page **Mon compte**).

**Requêtes.**

- Limite de débit globale par adresse, plus fine sur la connexion, l'inscription, les envois de fichiers et les webhooks.
- Taille des corps limitée (1 Mo en JSON, 32 Mo pour les fichiers) ; images vérifiées par leur signature d'octets et leur taille en pixels.
- `Idempotency-Key` : une action rejouée (double appui, renvoi hors connexion) n'est exécutée qu'une fois.
- En-têtes : CSP, HSTS, `X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` (API et web).

**Médias.** Les liens de photos et de récits sont signés et expirent au bout de 6 heures (ou liens présignés S3). Une publication ne peut citer que des médias de sa propre famille.

**Journaux inaltérables.** `audit_log` (actions dans les familles), `platform_audit` (actions de l'opérateur) et `security_event` sont en ajout seul : des déclencheurs refusent toute modification ou suppression, même par l'application.

**Production.** Avec `ENVIRONMENT=production`, l'API refuse de démarrer si le secret JWT ou celui des webhooks est faible, si CORS contient `*` ou une adresse HTTP, ou si les adresses publiques ne sont pas en HTTPS. La documentation interactive `/docs` est désactivée.

**Dépendances (27 octobre 2026).** `bandit` : aucun problème de gravité moyenne ou haute. `pip-audit` : aucune vulnérabilité connue. Web : `path-to-regexp` forcé en 8.4.2 (0 vulnérabilité). Mobile : `zod` 3 vulnérable, mais seulement dans `@expo/cli`, l'outil de compilation ; il n'est pas embarqué dans l'application. À suivre à la prochaine version d'Expo.

## 5. Hors connexion (mobile)

- À l'ouverture d'une famille et au retour au premier plan, le téléphone charge l'arbre, les personnes, le fil, la mémoire, les collectes ouvertes et leurs cotisations.
- Sans réseau : lecture de tout cela, recherche dans l'arbre, fiche reconstituée depuis l'arbre.
- Les actions (publier, commenter, réagir, voter, proposer, déclarer un paiement, relire un texte, valider) partent dans une **file d'envoi** gardée sur le téléphone, chacune avec sa clé d'idempotence.
- La file repart dans l'ordre au retour du réseau (changement de connectivité, retour au premier plan, essai toutes les 15 s). Une action refusée par le serveur (droits, validation) reste visible dans **Envois en attente** avec la raison ; l'utilisateur peut la relancer ou l'abandonner.
- Vérifié : une publication, une réaction, un vote et un paiement faits sans réseau arrivent chacun une seule fois au retour de la connexion.
- La déconnexion vide la file et le cache.

## 6. Supervision de la plateforme

L'opérateur de la plateforme est désigné en ligne de commande, jamais depuis l'application :

```bash
python -m app.cli operator add votre@adresse.com
python -m app.cli operator list
python -m app.cli operator remove votre@adresse.com
```

La page **Supervision** (web, `/supervision`, lien dans **Mon compte**) montre :

- **Vue d'ensemble** : comptes, familles, trafic des 24 dernières heures, erreurs, état de la base, du stockage, de la messagerie, isolement des familles actif ;
- **Sécurité** : événements (connexions refusées, comptes verrouillés, rejeux de jetons, accès à une autre famille, signatures de webhook invalides) ;
- **Comptes** : recherche, suspension, réactivation, déverrouillage, fermeture des sessions (avec motif obligatoire) ;
- **Familles** : nombres de membres, personnes, publications et date de dernière activité ;
- **Journal de l'opérateur** : chaque consultation et chaque action de l'opérateur, inaltérable.

L'opérateur ne voit jamais le contenu des familles (arbre, publications, récits, montants).
