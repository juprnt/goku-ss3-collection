# Goku SS3 Collection

Application web mono-page (pas de framework, pas de build) pour cataloguer et gérer
une collection personnelle de cartes "Son Goku Super Saiyan 3" (Dragon Ball Super
Card Game et jeux apparentés).

## Stack technique

- **Frontend** : HTML + CSS + JavaScript vanilla, tout dans un seul fichier
  [`index.html`](./index.html). Aucune étape de build, aucun bundler.
- **Backend** : [Supabase](https://supabase.com) (Postgres + Auth + Storage), projet
  `vtdohksscretlbvhsgfo`, accédé côté client via le SDK
  [`@supabase/supabase-js`](https://github.com/supabase/supabase-js) chargé depuis le
  CDN unpkg (version épinglée, voir plus bas).
- **Hébergement** : déploiement statique automatique sur [Vercel](https://vercel.com),
  lié au dépôt GitHub `juprnt/goku-ss3-collection` (push sur `main` = déploiement).
- **Auth** : email/mot de passe via Supabase Auth. La clé utilisée côté client
  (`SUPABASE_ANON_KEY`) est la clé publique anonyme — elle est censée être visible
  côté client ; la sécurité réelle des données repose sur les policies RLS
  (Row Level Security) configurées côté Supabase, pas sur le secret de cette clé.

## Fichiers du dépôt

| Fichier       | Rôle                                                              |
|---------------|--------------------------------------------------------------------|
| `index.html`  | Toute l'application (CSS inline + JS inline).                     |
| `logo.png`    | Logo de l'app, utilisé comme favicon, apple-touch-icon et logo UI.|
| `README.md`   | Ce fichier.                                                        |

## Tables Supabase utilisées

- `public.cards` — catalogue de référence des cartes (une ligne = une carte connue,
  toutes éditions confondues). Colonne `review_status` : `confirmed` (visible dans
  l'onglet Catalogue) ou `pending_review` (en attente de validation, onglet
  "Cartes à valider").
- `public.games` / `public.game_sets` — hiérarchie Jeu → Extension utilisée pour
  regrouper l'affichage du catalogue.
- `public.collection_items` — les cartes possédées / en wishlist par l'utilisateur
  connecté (données personnelles).
- `public.card_photos` — photos recto/verso associées à un `collection_item`,
  stockées dans le bucket Storage privé `card-photos` (accès via URL signée).
- `public.hidden_cards` — cartes du catalogue masquées par l'utilisateur.

**Ne jamais toucher `collection_items` ou `card_photos` en dehors d'une action
explicite de l'utilisateur concerné** — ce sont des données personnelles.

## Fonctionnement de l'app (`index.html`)

Un seul fichier statique, servi tel quel par Vercel. Au chargement :

1. `checkSession()` vérifie si une session Supabase existe déjà (cookie/local
   storage géré par le SDK) et connecte automatiquement l'utilisateur si oui.
2. Une fois connecté, `loadAll()` charge en parallèle (`Promise.all`) : le
   catalogue confirmé, la file de validation, la collection de l'utilisateur, les
   cartes masquées et la hiérarchie jeux/extensions — puis déclenche le premier
   rendu de tous les onglets.
3. Chaque onglet (`Tableau de bord`, `Ma collection`, `Wishlist`,
   `Catalogue de référence`, `Cartes à valider`) a sa propre fonction de rendu
   (`renderDashboard`, `renderCollectionGrid`, etc.) qui reconstruit son HTML à
   partir des données déjà chargées en mémoire (pas de requête réseau
   supplémentaire, sauf pour résoudre les URLs de photos).

Les photos de collection sont privées : chaque affichage résout une URL signée
via `getPhotoUrl()`, mise en cache côté client (voir section Optimisations).

## Historique des optimisations (23/08/2026)

Une passe de nettoyage a été appliquée sur `index.html`. Résumé des changements,
pour référence future :

- **Cache + parallélisation des URLs de photos signées.** `getPhotoUrl()` met
  désormais en cache chaque URL signée (`photoUrlCache`, clé = `storage_path`,
  durée de vie ~50 min, un peu sous les 60 min de validité côté Supabase).
  `renderGrid()` (grilles Collection / Wishlist) résout tous les items d'un
  rendu avec `Promise.all` au lieu d'un `for...of` avec `await` séquentiel —
  auparavant, chaque frappe dans la recherche pouvait déclencher N appels
  réseau Supabase Storage en série pour re-générer des URLs déjà valides.
- **Debounce des champs de recherche** (`col-search`, `review-search`,
  `wish-search`, `cat-search`) : 200ms d'inactivité avant de relancer le rendu,
  au lieu de re-render à chaque caractère tapé.
- **Version du SDK Supabase épinglée** : `@supabase/supabase-js@2.112.3` au lieu
  de `@2` (flottant), pour éviter qu'une future version majeure/mineure cassante
  du CDN ne casse le site sans prévenir. À mettre à jour manuellement de temps en
  temps (`npm view @supabase/supabase-js version` pour connaître la dernière
  version stable).
- **Logo externalisé** : le logo était encodé en base64 (~14 Ko) directement
  dans le HTML/JS (`LOGO_DATA_URI`), alourdissant chaque chargement de page et
  empêchant tout cache navigateur séparé. Il est maintenant un fichier
  `logo.png` à la racine du dépôt, référencé via `/logo.png` (favicon,
  apple-touch-icon, logo dans l'en-tête et l'écran de connexion).
- **`loading="lazy"` ajouté** sur les images des grilles (collection, wishlist,
  catalogue, review) et sur les logos jeux/extensions du catalogue, pour éviter
  de charger toutes les images hors-écran au premier rendu.
- **Nettoyage mineur** : suppression de la règle CSS morte `.modal .close-x`
  (classe jamais utilisée dans le HTML) ; renommage de la variable locale
  `displayName` dans `renderCatalogueGrid()` en `setDisplayName` pour ne plus
  masquer la fonction globale du même nom.

Validation effectuée avant déploiement : vérification syntaxique JS
(`node --check`), et test de chargement de la page dans Chromium headless
(0 erreur console/réseau, favicon et logo chargés, cache et debounce présents).

### Pistes non traitées (volontairement laissées de côté)

Rien de bloquant, mais à garder en tête si le catalogue grossit beaucoup :

- Pas de pagination sur les grilles — au-delà de quelques centaines de cartes,
  le rendu complet à chaque recherche pourrait devenir sensible.
- Pas d'écoute `onAuthStateChange` — un token expiré en cours de session n'est
  pas géré automatiquement (l'utilisateur devrait recharger la page).
