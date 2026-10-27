# 04 — Déploiement (offres gratuites)

> Version 1.0 — 27 octobre 2026

Trois services gratuits, tous reliés au dépôt GitHub : **Neon** pour PostgreSQL, **Render** pour l'API, **Vercel** pour le web. Chaque `git push` sur `main` lance la CI (tests API, build web, typage mobile) puis redéploie l'API et le web.

```mermaid
flowchart LR
  GH[GitHub MF-SHEENU] -- push main --> CI[GitHub Actions]
  GH -- Blueprint render.yaml --> R[Render : API]
  GH -- dossier web/ --> V[Vercel : web]
  R --> N[(Neon : PostgreSQL)]
  V -- VITE_API_URL --> R
```

## 1. Base de données : Neon

1. Créer un compte sur neon.tech, puis un projet `sheenu` (région la plus proche : Francfort).
2. Dans l'éditeur SQL de Neon, créer un rôle **dédié à l'application, sans contournement de la RLS** :

   ```sql
   CREATE ROLE sheenu_app WITH LOGIN PASSWORD 'un-mot-de-passe-long' NOBYPASSRLS;
   GRANT ALL ON DATABASE neondb TO sheenu_app;
   GRANT ALL ON SCHEMA public TO sheenu_app;
   ```

   Pourquoi : le rôle propriétaire créé par Neon peut contourner la Row Level Security. Avec lui, l'isolation entre familles ne serait plus garantie par la base.
3. Copier la chaîne de connexion en remplaçant l'utilisateur par `sheenu_app` :
   `postgresql://sheenu_app:MOTDEPASSE@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`

## 2. API : Render

1. Créer un compte sur render.com en se connectant avec GitHub.
2. **New → Blueprint**, choisir le dépôt `MF-SHEENU`. Render lit `render.yaml` et crée le service `sheenu-api`.
3. Renseigner les variables demandées :

   | Variable | Valeur |
   |---|---|
   | `DATABASE_URL` | la chaîne Neon de l'étape 1 |
   | `CORS_ORIGINS` | l'adresse du web, par exemple `https://sheenu.vercel.app` |
   | `PUBLIC_WEB_URL` | la même adresse (sert aux liens d'invitation) |
   | `PUBLIC_API_URL` | l'adresse de l'API, par exemple `https://sheenu-api.onrender.com` |

   `JWT_SECRET` est généré automatiquement.
4. Au premier démarrage, l'API applique les migrations. Vérifier `https://sheenu-api.onrender.com/health` : il doit répondre `"rls_enforced": true`. Si la valeur est `false`, la chaîne de connexion utilise un rôle qui contourne la RLS : revoir l'étape 1.

**Limites de l'offre gratuite** : le service se met en veille après 15 minutes sans requête ; le premier appel suivant prend environ une minute. Le disque n'est pas persistant : les photos doivent aller sur Cloudflare R2 (section 4) avant l'ouverture à la grande famille.

## 3. Web : Vercel

1. Créer un compte sur vercel.com avec GitHub, **Add New → Project**, choisir `MF-SHEENU`.
2. **Root Directory** : `web`. Framework détecté : Vite.
3. Variable d'environnement : `VITE_API_URL` = l'adresse de l'API Render.
4. Déployer. `web/vercel.json` renvoie toutes les routes vers l'application (liens d'invitation `/rejoindre/...` compris).

Alternative équivalente : Cloudflare Pages (le fichier `web/public/_redirects` est déjà prêt).

## 4. Photos : Cloudflare R2 (avant l'ouverture à la grande famille)

1. Cloudflare → R2 → créer le bucket `sheenu-media`, activer l'accès public (domaine `r2.dev`).
2. Créer un jeton API R2 (lecture et écriture sur ce bucket).
3. Sur Render, définir : `STORAGE_BACKEND=s3`, `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_PUBLIC_URL`.

## 4 bis. Messagerie et paiement en ligne (phase 6, facultatif)

Par défaut, rien de payant n'est branché :

- `MESSAGING_BACKEND=share` : les rappels de cotisation et le résumé de la semaine sont préparés en liens WhatsApp que le trésorier ou le secrétaire ouvre lui-même ;
- `PAYMENT_BACKEND=none` : les paiements restent déclarés à la main et validés par le trésorier.

Pour envoyer directement par l'**API WhatsApp Business** (payante, compte Meta Business vérifié) : `MESSAGING_BACKEND=whatsapp_cloud`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`. Prévoir des modèles de message approuvés par Meta pour écrire hors de la fenêtre de 24 heures.

Pour le **Mobile Money** : écrire la classe du prestataire choisi dans `api/app/integrations/payments.py` (deux méthodes, `start` et `parse_webhook`), l'ajouter dans `get_gateway()`, puis déclarer l'adresse du webhook chez le prestataire : `https://<api>/api/v1/webhooks/payments/<nom>`. `PAYMENT_BACKEND=sandbox` permet de tout essayer sans argent réel. `PAYMENT_WEBHOOK_SECRET` (généré par Render) signe les webhooks.

## 5. Premier lancement

1. Ouvrir le web, **Créer un compte**, puis **Créer l'espace d'une famille** : vous en êtes l'administrateur.
2. Ajouter l'ancêtre racine, ouvrir sa fiche, **Plus → Définir comme racine**.
3. Créer les titres (**Titres**), puis inviter les membres depuis leur fiche (**Plus → Inviter sur Sheenu**) : le message se partage directement sur WhatsApp.

## 6. Application mobile

En développement :

```bash
cd mobile
npm install
EXPO_PUBLIC_API_URL=https://sheenu-api.onrender.com npx expo start
```

Les testeurs installent **Expo Go** et scannent le QR code. Pour une version installable (APK Android), utiliser EAS Build (offre gratuite) : `npx eas build -p android --profile preview`.

## 7. Sauvegardes

Neon conserve un historique de restauration sur l'offre gratuite. En complément, l'export **GEDCOM** (menu **Télécharger** de l'arbre) produit une copie complète et portable de l'arbre ; à faire régulièrement par l'administrateur.
