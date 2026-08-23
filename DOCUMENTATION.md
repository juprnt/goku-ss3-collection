# Goku SS3 Card Collection — Documentation

_Dernière mise à jour : 23 août 2026_

## 1. Résumé

Application web à page unique pour cataloguer et suivre une collection personnelle de cartes à jouer représentant **Son Goku en Super Saiyan 3**, toutes éditions et tous jeux Dragon Ball confondus (Carddass, Dragon Ball Heroes, Dragon Ball Super Card Game...).

- **URL de production :** https://goku-ss3-collection.vercel.app/
- **Repo GitHub :** `juprnt/goku-ss3-collection`
- **Projet Vercel :** `goku-ss3-collection` (équipe `juprnts-projects`)
- **Projet Supabase :** `goku-ss3-collection` (ref `vtdohksscretlbvhsgfo`, région `eu-west-3`)

## 2. Stack technique

- **Frontend :** trois fichiers statiques à la racine du dépôt — `index.html` (HTML + CSS + JS vanilla, aucune étape de build), `logo.png` (logo de l'app) et `README.md`. Le JS est écrit en `<script>` classique (pas de modules ES, pas de bundler).
- **Client Supabase :** chargé via CDN, version épinglée (`https://unpkg.com/@supabase/supabase-js@2.112.3`) plutôt que flottante, pour éviter qu'une mise à jour du CDN casse le site sans prévenir. Initialisé avec l'URL du projet et la clé `anon` publique (sans danger à exposer côté client : toutes les tables ont Row Level Security activé).
- **Backend :** Supabase (Postgres + Auth + Storage).
- **Hébergement :** Vercel (déploiement de fichier statique, sans framework détecté).

Aucune dépendance npm, aucun système de build : modifier `index.html` (ou `logo.png`) = modifier toute l'application.

## 3. Authentification

Email + mot de passe via `supabase.auth` (`signUp` / `signInWithPassword`). Chaque compte est isolé : les données de collection (`collection_items`, `card_photos`, `hidden_cards`) sont scoping par `user_id` et protégées par RLS. Le catalogue de référence (`cards`, `games`, `game_sets`) est partagé entre tous les utilisateurs (lecture commune).

## 4. Modèle de données (Supabase / Postgres, schéma `public`)

### `games` (4 lignes)
Les "jeux" de haut niveau. Clé primaire `slug`.

| slug | name | subtitle | cartes cataloguées |
|---|---|---|---|
| `carddass` | Carddass | Bandai — cartes rétro (DB / DBZ / GT) | 16 |
| `dbh` | Dragon Ball Heroes | Bandai — jeu de cartes arcade | 5 |
| `dbscg-masters` | Dragon Ball Super Card Game | Masters | 55 |
| `dbscg-fusion` | Dragon Ball Super Card Game | Fusion World | 4 |

### `game_sets` (349 lignes)
Séries / extensions à l'intérieur d'un jeu (`game_slug` + `set_name`, avec `display_name` et `sort_order` pour l'affichage).

### `cards` (80 lignes)
Le catalogue de référence. Colonnes clés : `game`, `game_slug` (FK → `games.slug`), `set_name`, `set_code`, `card_number`, `card_name`, `rarity`, `card_type`, `color`, `language`, `release_date`, `official_image_url`, `source_url`, `notes`, `review_status` (`confirmed` / `pending_review` / `rejected`), `review_source`.

Les cartes en `pending_review` proviennent d'une détection automatique (ex. reconnaissance sur dbzcollection.fr) et apparaissent dans l'onglet **Cartes à valider** avant d'intégrer le catalogue officiel.

### `collection_items` (0 ligne — vide en prod actuellement)
Les cartes possédées ou en wishlist par un utilisateur. `status` = `owned` / `wishlist`. Champs : `card_id` (optionnel, FK → `cards.id`), `custom_name` (si la carte n'est pas cataloguée), `quantity`, `condition`, `language_override`, `grading_company`, `grading_score`, `price_paid`, `estimated_value`, `currency`, `acquired_date`, `notes`.

### `card_photos` (0 ligne)
Photos recto/verso liées à un `collection_items.id`, stockées dans le bucket Storage `card-photos` (accès via URL signée, 1h de validité).

### `hidden_cards` (17 lignes)
Table de jointure `user_id` + `card_id` : permet à un utilisateur de masquer une carte du catalogue sans la supprimer (utile si le catalogue contient une carte qui n'intéresse pas cet utilisateur). Réversible via "Afficher les cartes masquées".

## 5. Fonctionnalités (onglets de l'app)

1. **Tableau de bord** — statistiques : nombre de cartes possédées, quantité totale, valeur estimée, total dépensé, wishlist, taille du catalogue, répartition par jeu.
2. **Ma collection** — liste des cartes possédées, recherche, filtres (jeu, état), vérification rapide "est-ce que je possède déjà cette carte ?", ajout/édition avec photos recto/verso.
3. **Wishlist** — cartes souhaitées, recherche.
4. **Catalogue de référence** — toutes les cartes connues. Deux menus déroulants **Jeu** et **Série** (tous deux "tout sélectionné" par défaut) filtrent une grille plate de cartes (3 colonnes en mobile, 4 en tablette, responsive au-delà) ; case à cocher pour afficher les cartes masquées. Chaque carte a un badge Possédée/Manquante et un bouton Masquer/Réafficher.
5. **Cartes à valider** — file de modération pour les cartes détectées automatiquement (pas encore dans le catalogue officiel), avec boutons Valider / Rejeter.

## 6. Déploiement

Le projet Vercel **n'est pas lié à Git** — les déploiements se font via l'outil MCP `deploy_to_vercel` (upload direct de fichiers), pas via un `git push` qui déclencherait un build automatique.

⚠️ **Point d'attention connu :** le repo GitHub `juprnt/goku-ss3-collection` n'est pas dans la liste des dépôts autorisés pour l'agent (proxy git de la session Cowork), donc `git push` échoue avec une erreur 403 malgré une autorisation verbale de l'utilisateur. Il faudrait qu'un(e) administrateur(trice) ajoute ce dépôt dans les "sources" connectées de la session pour que les prochains push fonctionnent normalement. En attendant, le dépôt local a un historique à jour (voir commit `e62042c` et suivants) mais **en avance sur `origin/main`** — à pousser dès que l'accès sera débloqué.

Pour déployer manuellement sans passer par Git : appeler `deploy_to_vercel` avec le contenu complet de `index.html` en pièce jointe (target `production`, projet `goku-ss3-collection`, équipe `team_ZssdCPrqch7AkpYwYH9YpoqH`).

### Logo de l'application

Le logo ("EDITION" + silhouette de Goku SS3, fond doré) est un fichier externe `logo.png` (120×120) à la racine du dépôt, référencé via `/logo.png` (favicon, apple-touch-icon, logo de l'écran de connexion et de la topbar). Il a d'abord été encodé en `data:` URI directement dans `index.html` (variable `LOGO_DATA_URI`) pour éviter une dépendance à un fichier externe, mais cette chaîne base64 (~17 500 caractères) s'est corrompue à plusieurs reprises lors de sa réinsertion manuelle dans les appels de déploiement — elle a donc été externalisée en fichier statique servi tel quel par Vercel, ce qui élimine ce risque et permet en plus la mise en cache navigateur du logo indépendamment du HTML.

## 7. Historique des principaux problèmes résolus

- **Cartes qui n'apparaissaient plus** : diagnostiqué comme un problème d'authentification / RLS Supabase, pas une perte de données.
- **Logo cassé (placeholder `REPLACE_ME_LOGO` resté en prod, puis corruptions répétées de la chaîne base64)** : stabilisé définitivement en externalisant le logo dans `logo.png` plutôt qu'en le ré-encodant à chaque déploiement.
- **Refonte du catalogue** : remplacement de l'arborescence Jeu → Série (accordéon, avec expand/collapse) par deux filtres déroulants indépendants (**Jeu** / **Série**) + une grille plate, pour une navigation plus rapide. Cette refonte avait été perdue par erreur lors d'un nettoyage de code fait dans une conversation parallèle (le fichier réintroduisait l'ancienne arborescence) ; elle a été restaurée le 23/08/2026 en fusionnant les deux lignées de code, en conservant les améliorations de performance de l'entretemps (voir ci-dessous).
- **Passe de nettoyage et de performance (23/08/2026)** : cache des URLs de photos signées (`photoUrlCache`, ~50 min de durée de vie) + résolution en parallèle (`Promise.all`) dans les grilles Collection/Wishlist au lieu d'un `await` séquentiel ; debounce de 200ms sur les quatre champs de recherche ; version du SDK Supabase épinglée (`@2.112.3`) ; `loading="lazy"` sur les images des grilles ; suppression de la règle CSS morte `.modal .close-x` ; renommage d'une variable locale masquant une fonction globale du même nom (`displayName` → `setDisplayName`).

## 8. Structure du fichier `index.html`

- `<head>` : meta, titre, favicon/apple-touch-icon (`/logo.png`).
- `<style>` : variables CSS (`:root`), styles de l'écran d'authentification, de la topbar, des onglets, des grilles de cartes, des media queries mobile/tablette, de la modale d'ajout/édition, des toasts.
- `<body>` : écran d'authentification, coquille de l'app (topbar + onglets + 5 panneaux), modale d'ajout/édition, conteneur de toasts.
- `<script>` : initialisation Supabase, gestion de session/auth, chargement des données (`loadAll`), cache des URLs de photos (`getPhotoUrl`), rendu des grilles (`renderGrid`, `renderCatalogueGrid`, `renderReviewGrid`), filtres (`populateFilters`, `populateCatalogueFilters`), modale, upload de photos, utilitaires (`debounce`, `escapeHtml`, `gameDisplayName`).

## 9. Pistes pour la suite

- Débloquer l'accès Git pour repasser en flux normal `git push` → déploiement (actuellement en accès direct via l'outil de déploiement).
- Envisager de lier le projet Vercel au repo GitHub (`create_git_project`) une fois l'accès Git débloqué, pour des déploiements automatiques à chaque push.
- Continuer à enrichir le catalogue de référence (80 cartes actuellement) au fil des photos envoyées par l'utilisateur.
- Pas de pagination sur les grilles — à surveiller si le catalogue grossit beaucoup au-delà de quelques centaines de cartes.
- Pas d'écoute `onAuthStateChange` — un token expiré en cours de session n'est pas géré automatiquement (l'utilisateur doit recharger la page).
