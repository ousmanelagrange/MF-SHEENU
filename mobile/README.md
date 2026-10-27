# Sheenu mobile (Expo)

## Écrans

| Onglet | Contenu |
|---|---|
| Personnes | Liste par préséance, recherche, chargement progressif |
| Arbre | Descendance ou ascendance, profondeur et zoom réglables, toucher une personne ouvre sa fiche |
| Propositions | Accepter ou refuser (avec motif) les propositions à valider ; suivre les siennes |
| Moi | Ma fiche, changer de famille, se déconnecter |

La fiche d'une personne s'ouvre par-dessus les onglets : identité, lien avec moi, histoire, parents, conjoints, enfants, fratrie.

## Organisation du code

```
App.tsx               polices, session, connexion ou navigation
src/navigation.tsx    pile (familles, onglets, fiche) et onglets
src/screens/          un fichier par écran
src/components/       briques d'interface et icônes
src/treeLayout.ts     mise en page de l'arbre (identique au web)
src/api.ts            client HTTP, jetons conservés sur l'appareil
```

## Lancer

```bash
npm install
EXPO_PUBLIC_API_URL=http://<IP-de-votre-ordinateur>:8000 npx expo start
```

Ouvrez Expo Go sur le téléphone et scannez le QR code.
