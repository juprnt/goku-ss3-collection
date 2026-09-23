# Goku SS3 Collection

> ⚠️ **Site web abandonné le 23/09/2026 : projet Vercel `goku-ss3-collection` **mis en pause** (le site répond 503). L'app s'utilise désormais via l'**APK Android** (`mobile/`). Réactivable en un clic dans le dashboard Vercel si besoin.**

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
- **Hébergement** : ~~Vercel~~ — abandonné le 23/09/2026 (projet mis en pause). L'app est
  distribuée comme APK Android construit par [`mobile/build.sh`](./mobile/build.sh) à partir
  de `index.html`. Un push sur `main` ne publie donc plus rien.
- **Auth** : email/mot de passe via Supabase Auth. La clé utilisée côté client
  (`SUPABASE_ANON_KEY`) est la clé publique anonyme — elle est censée être visible
  côté client ; la sécurité réelle des données repose sur les policies RLS
  (Row Level Security) configurées côté Supabase, pas sur le secret de cette clé.

## Fichiers du dépôt

| Fichier             | Rôle                                                                 |
|----------------------|----------------------------------------------------------------------|
| `index.html`         | Toute l'application (CSS inline + JS inline).                       |
| `logo.png`           | Logo de l'app, utilisé comme favicon, apple-touch-icon et logo UI.  |
| `README.md`          | Ce fichier — vue d'ensemble rapide.                                  |
| `DOCUMENTATION.md`   | Documentation détaillée (schéma de données, historique complet, déploiement). |
| `ai-server/`         | Serveur IA local (Mac mini + Ollama) : reconnaissance de cartes et recherche en langage naturel. Exclu du déploiement Vercel via `.vercelignore`. Voir [`ai-server/README.md`](./ai-server/README.md). |
| `mobile/`            | App Android (Capacitor) : `build.sh` génère l'APK à partir de `index.html`. Exclu du déploiement Vercel. Voir [`mobile/README.md`](./mobile/README.md). |

## Tables Supabase utilisées

- `public.cards` — catalogue de référence des cartes (une ligne = une carte connue,
  toutes éditions confondues). Colonne `review_status` : `confirmed` (visible dans
  l'onglet Catalogue) ou `pending_review` (en attente de validation, onglet
  "Cartes à valider"). 115 cartes confirmées au 23/09/2026.
- `public.games` / `public.game_sets` — hiérarchie Jeu → Extension utilisée pour
  regrouper l'affichage du catalogue. `game_sets.sort_order` reflète l'ordre
  chronologique réel de sortie de chaque extension (du plus ancien au plus récent).
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

## Période de test en cours

Le projet entre dans une phase de test utilisateur de plusieurs semaines. Pour tout
bug ou comportement inattendu rencontré pendant cette période, le plus simple est de
créer une entrée dans l'onglet **Issues** du dépôt GitHub
(`github.com/juprnt/goku-ss3-collection/issues`) — ça garde un historique daté et
évite de perdre le contexte d'une session à l'autre.

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

## Historique des correctifs (23/08/2026, passe 2)

- **Favicon invisible sur PC (Chrome/Edge desktop)** : le favicon pointait vers
  `/logo.png` sans paramètre de version, donc un navigateur ayant mis en cache une
  version précédente (ou une réponse d'erreur) ne rechargeait jamais l'icône.
  Corrigé avec un cache-busting (`?v=6`) sur toutes les balises favicon /
  apple-touch-icon / logo (`<img>` écran de connexion et en-tête).
- **Incident logo corrompu en production** : un déploiement manuel de fichiers a
  brièvement remplacé `logo.png` par une image corrompue en production. Le dépôt
  GitHub, lui, n'a jamais été touché et contenait toujours le bon fichier. Résolu
  en promouvant en production le déploiement Git existant (déjà construit à partir
  du bon `logo.png`), sans jamais retransmettre le fichier binaire manuellement.
  Voir `DOCUMENTATION.md` §7 pour le détail et la leçon à en tirer.
- **Cartes manquantes (Dragon Ball Super Card Game Fusion World)** : passe de
  recherche sur Cardmarket / dragonball.gg pour identifier des cartes "Son Goku
  SS3" absentes du catalogue ; ajout de 3 cartes (New Adventure FB05, Wish for
  Shenron FB07, Dual Evolution FB09) et remplacement d'une image basse résolution
  par une version plus grande. Catalogue confirmé : 83 cartes (était 80).
- **Ordre de tri des extensions Fusion World** : `game_sets.sort_order` mis à jour
  en base pour refléter l'ordre chronologique réel de sortie (du plus ancien —
  Awakened Pulse — au plus récent — Brightness of Hope). Le code de tri
  (`renderCatalogueGrid`, `populateCatalogueFilters`) existait déjà et s'appuie sur
  cette colonne — seule la donnée a été corrigée.
- **Confirmation du lien Git ↔ Vercel** : le projet Vercel est bien relié au dépôt
  GitHub (`git push` sur `main` = déploiement automatique en production). C'est ce
  lien qui a permis de résoudre l'incident du logo sans risque.

### Pistes non traitées (volontairement laissées de côté)

Rien de bloquant, mais à garder en tête si le catalogue grossit beaucoup :

- Pas de pagination sur les grilles — au-delà de quelques centaines de cartes,
  le rendu complet à chaque recherche pourrait devenir sensible.
- Pas d'écoute `onAuthStateChange` — un token expiré en cours de session n'est
  pas géré automatiquement (l'utilisateur devrait recharger la page).
