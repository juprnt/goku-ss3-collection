# Goku SS3 Card Collection — Documentation

_Dernière mise à jour : 23 août 2026_

## 1. Résumé

Application web à page unique pour cataloguer et suivre une collection personnelle de cartes à jouer représentant **Son Goku en Super Saiyan 3**, toutes éditions et tous jeux Dragon Ball confondus (Carddass, Dragon Ball Heroes, Dragon Ball Super Card Game...).

- **URL de production :** https://goku-ss3-collection.vercel.app/
- **Repo GitHub :** `juprnt/goku-ss3-collection`
- **Projet Vercel :** `goku-ss3-collection` (équipe `juprnts-projects`)
- **Projet Supabase :** `goku-ss3-collection` (ref `vtdohksscretlbvhsgfo`, région `eu-west-3`)
- **Statut :** en phase de test utilisateur (quelques semaines à partir du 23/08/2026) — voir §10.

## 2. Stack technique

- **Frontend :** trois fichiers statiques à la racine du dépôt — `index.html` (HTML + CSS + JS vanilla, aucune étape de build), `logo.png` (logo de l'app) et les fichiers Markdown de doc. Le JS est écrit en `<script>` classique (pas de modules ES, pas de bundler).
- **Client Supabase :** chargé via CDN, version épinglée (`https://unpkg.com/@supabase/supabase-js@2.112.3`) plutôt que flottante, pour éviter qu'une mise à jour du CDN casse le site sans prévenir. Initialisé avec l'URL du projet et la clé `anon` publique (sans danger à exposer côté client : toutes les tables ont Row Level Security activé).
- **Backend :** Supabase (Postgres + Auth + Storage).
- **Hébergement :** Vercel, **projet lié au dépôt GitHub** (voir §6).

Aucune dépendance npm, aucun système de build : modifier `index.html` (ou `logo.png`) = modifier toute l'application.

## 3. Authentification

Email + mot de passe via `supabase.auth` (`signUp` / `signInWithPassword`). Lien **Mot de passe oublié ?** (`resetPasswordForEmail`, retour sur l'URL courante) : à l'ouverture du lien reçu par email, l'événement `PASSWORD_RECOVERY` affiche un formulaire de nouveau mot de passe (`updateUser`). Prérequis côté Supabase : **Site URL** / **Redirect URLs** (Authentication › URL Configuration) doivent contenir `https://goku-ss3-collection.vercel.app`. Chaque compte est isolé : les données de collection (`collection_items`, `card_photos`, `hidden_cards`) sont scoping par `user_id` et protégées par RLS. Le catalogue de référence (`cards`, `games`, `game_sets`) est partagé entre tous les utilisateurs (lecture commune).

## 4. Modèle de données (Supabase / Postgres, schéma `public`)

### `games` (4 lignes)
Les "jeux" de haut niveau. Clé primaire `slug`.

| slug | name | subtitle | cartes confirmées |
|---|---|---|---|
| `carddass` | Carddass | Bandai — cartes rétro (DB / DBZ / GT) | 16 |
| `dbh` | Dragon Ball Heroes | Bandai — jeu de cartes arcade | 5 |
| `dbscg-masters` | Dragon Ball Super Card Game | Masters | 55 |
| `dbscg-fusion` | Dragon Ball Super Card Game | Fusion World | 7 |

Total : **83 cartes confirmées** (80 avant la passe Cardmarket du 23/08/2026, voir §7).

### `game_sets` (349 lignes)
Séries / extensions à l'intérieur d'un jeu (`game_slug` + `set_name`, avec `display_name` et `sort_order` pour l'affichage). `sort_order` reflète l'ordre chronologique réel de sortie de chaque extension — c'est cette colonne qui pilote l'ordre d'affichage du catalogue (le code de tri lui-même n'a pas changé, seule la donnée a été corrigée pour Fusion World le 23/08/2026).

### `cards` (83 lignes confirmées)
Le catalogue de référence. Colonnes clés : `game`, `game_slug` (FK → `games.slug`), `set_name`, `set_code`, `card_number`, `card_name`, `rarity`, `card_type`, `color`, `language`, `release_date`, `official_image_url`, `source_url`, `notes`, `review_status` (`confirmed` / `pending_review` / `rejected`), `review_source`.

Les cartes en `pending_review` proviennent d'une détection automatique (ex. reconnaissance sur dbzcollection.fr) et apparaissent dans l'onglet **Cartes à valider** avant d'intégrer le catalogue officiel. 0 carte en attente actuellement.

### `collection_items` (0 ligne — vide en prod actuellement)
Les cartes possédées ou en wishlist par un utilisateur. `status` = `owned` / `wishlist`. Champs : `card_id` (optionnel, FK → `cards.id`), `custom_name` (si la carte n'est pas cataloguée), `quantity`, `condition`, `language_override`, `grading_company`, `grading_score`, `price_paid`, `estimated_value`, `currency`, `acquired_date`, `notes`.

### `card_photos` (0 ligne)
Photos recto/verso liées à un `collection_items.id`, stockées dans le bucket Storage `card-photos` (accès via URL signée, 1h de validité).

### `hidden_cards` (17 lignes)
Table de jointure `user_id` + `card_id` : permet à un utilisateur de masquer une carte du catalogue sans la supprimer (utile si le catalogue contient une carte qui n'intéresse pas cet utilisateur). Réversible via "Afficher les cartes masquées".

## 5. Fonctionnalités (onglets de l'app)

1. **Tableau de bord** — statistiques : nombre de cartes possédées, quantité totale, valeur estimée, total dépensé, wishlist, taille du catalogue, répartition par jeu.
2. **📷 Scanner & IA** — photo d'une carte (appareil photo ou galerie) → reconnaissance par le serveur IA local du Mac mini (voir `ai-server/README.md`) : cartes du catalogue correspondantes avec badge Possédée/Manquante, bouton **+ Ajouter** qui ouvre la fenêtre d'ajout pré-remplie avec la photo en recto. Plus une recherche en langage naturel (« mes cartes Masters en mauvais état »). Nécessite Tailscale actif sur l'appareil et le Mac mini allumé.
3. **Ma collection** — liste des cartes possédées, recherche, filtres (jeu, état), vérification rapide "est-ce que je possède déjà cette carte ?", ajout/édition avec photos recto/verso.
4. **Wishlist** — cartes souhaitées, recherche.
5. **Catalogue de référence** — toutes les cartes connues. Deux menus déroulants **Jeu** et **Série** (tous deux "tout sélectionné" par défaut) filtrent une grille plate de cartes (3 colonnes jusqu'à 480 px de large — téléphone, écran externe du Galaxy Z Fold —, 5 colonnes de 481 à 1100 px — écran interne déplié du Fold, petite tablette —, colonnes de ~220 px au-delà), triée par jeu puis par ordre chronologique d'extension (`game_sets.sort_order`) ; case à cocher pour afficher les cartes masquées. Chaque carte a un badge Possédée/Manquante et un bouton Masquer/Réafficher.
6. **Cartes à valider** — file de modération pour les cartes détectées automatiquement (pas encore dans le catalogue officiel), avec boutons Valider / Rejeter.

## 6. Déploiement

Le projet Vercel **est lié au dépôt GitHub** `juprnt/goku-ss3-collection` (branche `main`). Tout `git push` sur `main` déclenche automatiquement un build et un déploiement en production — **il n'y a pas d'étape de préversion/staging intermédiaire**, le déploiement écrase directement `goku-ss3-collection.vercel.app`. À garder en tête pendant la période de test : une modification poussée sur `main` est visible par tout le monde immédiatement.

GitHub reste la source de vérité : en cas de doute sur l'état réel de l'app en production, comparer avec le contenu de `main` sur GitHub plutôt qu'avec un déploiement manuel isolé.

### Pour un agent automatisé (Claude Code / Cowork) qui doit modifier ce dépôt

- **Préférer un vrai `git push`** sur `main` quand c'est possible : c'est le chemin normal, il laisse les fichiers binaires (`logo.png`) intacts et déclenche le déploiement automatique.
- Si `git push` échoue avec une erreur de proxy/autorisation (dépôt hors de la liste des sources autorisées de la session), une alternative fiable est l'**éditeur de fichiers web de GitHub** (`github.com/juprnt/goku-ss3-collection/edit/main/<fichier>`), qui permet de committer directement sans passer par le CLI local — mais seulement pour des fichiers texte (HTML/CSS/JS/Markdown). Attention : cet éditeur type le texte dans un CodeMirror où le raccourci Ctrl+F ne fait pas ce qu'on attend (il tape littéralement dans le document au lieu d'ouvrir une recherche) — utiliser le défilement à la souris pour naviguer, pas les raccourcis clavier de recherche/pagination.
- **Ne jamais réencoder `logo.png` (ou tout autre binaire) en base64 dans un appel d'outil de déploiement manuel.** Une chaîne base64 de ~17 500 caractères s'est corrompue à plusieurs reprises cette session lors de tentatives de retranscription en un seul passage, y compris juste après vérification — c'est une limite de fiabilité connue sur ce type de contenu à haute entropie, pas un problème ponctuel. Le fichier `logo.png` du dépôt GitHub n'a, lui, jamais été corrompu : en cas de doute sur l'état du logo en production, le plus sûr est de repartir de ce qui est sur `main` (via un vrai déploiement Git) plutôt que de le retransmettre à la main.
- Si un déploiement manuel (`deploy_to_vercel` ou équivalent) a pollué la production avec un fichier corrompu ou un contenu non désiré : le dépôt Git étant la source de vérité et le projet étant lié en Git, la façon la plus sûre de revenir à un état correct est de **promouvoir en production le dernier déploiement Git existant** (menu `...` → `Promote` sur le déploiement construit depuis `main`, dans le dashboard Vercel), plutôt que de retenter un nouveau déploiement manuel.

### Logo de l'application

Le logo ("EDITION" + silhouette de Goku SS3, fond doré) est un fichier externe `logo.png` (120×120, 13174 octets, sha256 `69050ab967f727aa803c92ca9660dcf859ba03c4a65fecfd268772d4fae48c16`) à la racine du dépôt, référencé via `/logo.png?v=6` (favicon, apple-touch-icon, logo de l'écran de connexion et de la topbar — le paramètre `?v=6` force les navigateurs à recharger l'icône plutôt que de garder une version mise en cache). C'est l'image de marque fournie par l'utilisateur — elle ne doit jamais être remplacée par une recréation/approximation sans demande explicite.

## 7. Historique des principaux problèmes résolus

- **Cartes qui n'apparaissaient plus** : diagnostiqué comme un problème d'authentification / RLS Supabase, pas une perte de données.
- **Refonte du catalogue** : remplacement de l'arborescence Jeu → Série (accordéon, avec expand/collapse) par deux filtres déroulants indépendants (**Jeu** / **Série**) + une grille plate, pour une navigation plus rapide. Cette refonte avait été perdue par erreur lors d'un nettoyage de code fait dans une conversation parallèle (le fichier réintroduisait l'ancienne arborescence) ; elle a été restaurée le 23/08/2026 en fusionnant les deux lignées de code, en conservant les améliorations de performance de l'entretemps.
- **Passe de nettoyage et de performance (23/08/2026)** : cache des URLs de photos signées (`photoUrlCache`, ~50 min de durée de vie) + résolution en parallèle (`Promise.all`) dans les grilles Collection/Wishlist au lieu d'un `await` séquentiel ; debounce de 200ms sur les quatre champs de recherche ; version du SDK Supabase épinglée (`@2.112.3`) ; `loading="lazy"` sur les images des grilles ; suppression de la règle CSS morte `.modal .close-x` ; renommage d'une variable locale masquant une fonction globale du même nom (`displayName` → `setDisplayName`). Le logo a été externalisé de `index.html` (variable `LOGO_DATA_URI` en base64) vers un fichier `logo.png` statique.
- **Favicon invisible sur PC (Chrome/Edge desktop)** : le favicon pointait vers `/logo.png` sans paramètre de version ; un navigateur ayant mis en cache une version précédente (ou une réponse d'erreur) ne rechargeait jamais l'icône. Corrigé le 23/08/2026 avec un cache-busting (`?v=6`) sur toutes les balises favicon / apple-touch-icon / logo.
- **Incident logo corrompu en production (23/08/2026)** : lors d'une tentative de correction manuelle, un déploiement de fichiers a brièvement remplacé `logo.png` par une image corrompue (transcription base64 ratée, voir §6). Le dépôt GitHub, jamais touché, contenait toujours le fichier correct. Résolu en promouvant en production le déploiement Git existant (déjà construit à partir du bon `logo.png`) via le dashboard Vercel, sans jamais retransmettre le binaire manuellement — puis en vérifiant le fichier livré en production par comparaison de hash SHA-256 avec l'original.
- **Cartes manquantes (Dragon Ball Super Card Game Fusion World)** : passe de recherche sur Cardmarket / dragonball.gg pour identifier des cartes "Son Goku SS3" absentes du catalogue ; ajout de 3 cartes (New Adventure FB05, Wish for Shenron FB07, Dual Evolution FB09) et remplacement d'une image basse résolution par une version plus grande. Catalogue confirmé : 83 cartes (était 80).
- **Ordre de tri des extensions Fusion World** : `game_sets.sort_order` mis à jour en base pour refléter l'ordre chronologique réel de sortie (du plus ancien — Awakened Pulse — au plus récent — Brightness of Hope). Le code de tri existait déjà et s'appuie sur cette colonne — seule la donnée a été corrigée.

## 8. Structure du fichier `index.html`

- `<head>` : meta, titre, favicon/apple-touch-icon/shortcut icon (`/logo.png?v=6`).
- `<style>` : variables CSS (`:root`), styles de l'écran d'authentification, de la topbar, des onglets, des grilles de cartes, des media queries mobile/tablette, de la modale d'ajout/édition, des toasts.
- `<body>` : écran d'authentification, coquille de l'app (topbar + onglets + 5 panneaux), modale d'ajout/édition, conteneur de toasts.
- `<script>` : initialisation Supabase, gestion de session/auth, chargement des données (`loadAll`), cache des URLs de photos (`getPhotoUrl`), rendu des grilles (`renderGrid`, `renderCatalogueGrid`, `renderReviewGrid`), filtres (`populateFilters`, `populateCatalogueFilters`), modale, upload de photos, utilitaires (`debounce`, `escapeHtml`, `gameDisplayName`).

## 9. Pistes pour la suite

- Continuer à enrichir le catalogue de référence (83 cartes actuellement) au fil des photos envoyées par l'utilisateur.
- Pas de pagination sur les grilles — à surveiller si le catalogue grossit beaucoup au-delà de quelques centaines de cartes.
- Pas d'écoute `onAuthStateChange` — un token expiré en cours de session n'est pas géré automatiquement (l'utilisateur doit recharger la page).
- 9 images Carddass/DBH orphelines identifiées mais non intégrées au catalogue (à confirmer avec l'utilisateur avant ajout).

## 10. Période de test (à partir du 23/08/2026)

Le projet entre dans une phase de test utilisateur de plusieurs semaines, sur l'app telle qu'elle est en production à cette date (logo correct, favicon fonctionnel, tri par jeu/extension chronologique, catalogue à 83 cartes).

- **Suivi des bugs :** utiliser l'onglet **Issues** du dépôt GitHub plutôt qu'une conversation isolée, pour garder un historique daté et consultable d'une session à l'autre.
- **Ce qui est considéré stable à ce stade :** authentification, catalogue de référence (affichage, filtres, tri), gestion de collection/wishlist (ajout, édition, photos), masquage de cartes, favicon/logo.
- **Ce qui n'a pas encore été testé en usage réel prolongé :** comportement au-delà de quelques centaines de cartes (pas de pagination), gestion d'un token de session expiré en cours d'usage (pas d'écoute `onAuthStateChange`), montée en charge du bucket Storage `card-photos`.
