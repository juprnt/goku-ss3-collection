# Goku SS3 Card Collection — Documentation

_Dernière mise à jour : 28 septembre 2026 (base de données passée de Supabase au Mac mini, v1.1)_

## 1. Résumé

Application web à page unique pour cataloguer et suivre une collection personnelle de cartes à jouer représentant **Son Goku en Super Saiyan 3**, toutes éditions et tous jeux Dragon Ball confondus (Carddass, Dragon Ball Heroes, Dragon Ball Super Card Game...).

- **Distribution :** APK Android (`mobile/build.sh`, version dans `mobile/package.json`).
- **Ancien site :** https://goku-ss3-collection.vercel.app/ — **abandonné** le 23/09/2026 (projet Vercel en pause, répond 503).
- **Repo GitHub :** `juprnt/goku-ss3-collection`
- **Projet Vercel :** `goku-ss3-collection` (équipe `juprnts-projects`) — **en pause / abandonné**
- **Base de données :** **PocketBase sur le Mac mini** depuis le 28/09/2026 (voir §14), accessible uniquement via Tailscale (`http://100.109.190.30:8092`).
- **Ancien projet Supabase :** `goku-ss3-collection` (ref `vtdohksscretlbvhsgfo`) — gardé **en pause 1 mois** après la bascule, par sécurité, puis à supprimer.
- **Statut :** en phase de test utilisateur (quelques semaines à partir du 23/08/2026) — voir §10.

## 2. Stack technique

- **Frontend :** trois fichiers statiques à la racine du dépôt — `index.html` (HTML + CSS + JS vanilla, aucune étape de build), `logo.png` (logo de l'app) et les fichiers Markdown de doc. Le JS est écrit en `<script>` classique (pas de modules ES, pas de bundler).
- **Accès aux données :** petit client maison dans `index.html` (`pbRequest`, `db.list/create/update/remove/createForm`) qui parle à l'API REST de PocketBase. Dans l'APK, les appels passent par `CapacitorHttp` (natif, pas de souci CORS / HTTP) ; dans un navigateur, par `fetch`. Aucun SDK.
- **Backend :** PocketBase 0.40 (SQLite + fichiers) sur le Mac mini, service launchd `com.goku.pocketbase`, dossier `~/Services/goku` (hors iCloud). Même principe que le projet Mariage & Baptême.
- **Hébergement de l'app :** APK Android (`mobile/`). L'ancien site Vercel est abandonné.

Aucune dépendance npm, aucun système de build : modifier `index.html` (ou `logo.png`) = modifier toute l'application.

## 3. Authentification

Email + mot de passe (collection `users` de PocketBase, `auth-with-password`). Le jeton est gardé dans `localStorage["goku-pb-auth"]` et rafraîchi au démarrage (`auth-refresh`). **Pas d'inscription publique** : le compte est créé par le superuser (il a été repris de Supabase avec le même identifiant, donc toutes les données restent liées). **Mot de passe oublié** : sur le Mac mini, `python3 ~/Services/goku/tools/set_password.py` (demande l'e-mail et le nouveau mot de passe, sans l'afficher). Données de collection (`collection_items`, `card_photos`, `hidden_cards`) : chacun ne voit que les siennes (règles `user_id = @request.auth.id`). Catalogue (`cards`, `games`, `game_sets`) : partagé entre comptes connectés.

## 4. Modèle de données (PocketBase ; schéma : `backend/pb_migrations/1790700000_schema.js`)

Les identifiants Supabase (UUID) ont été conservés ; l'id d'un jeu est son `slug`. Les images du catalogue autrefois sur Supabase Storage sont dans le champ fichier `cards.image` (sinon `official_image_url`, lien Bandai) ; les photos personnelles dans `card_photos.photo` (fichier **protégé**, lu avec un jeton de fichier temporaire).

### `games` (4 lignes)
Les "jeux" de haut niveau. Clé primaire `slug`.

| slug | name | subtitle | cartes confirmées |
|---|---|---|---|
| `carddass` | Carddass | Bandai — cartes rétro (DB / DBZ / GT) | 16 |
| `dbh` | Dragon Ball Heroes | Bandai — jeu de cartes arcade | 5 |
| `dbscg-masters` | Dragon Ball Super Card Game | Masters | 55 |
| `dbscg-fusion` | Dragon Ball Super Card Game | Fusion World | 39 |

Total : **115 cartes confirmées** + 1 en attente de validation (83 avant la passe base officielle Bandai du 23/09/2026, voir §7).

### `game_sets` (349 lignes)
Séries / extensions à l'intérieur d'un jeu (`game_slug` + `set_name`, avec `display_name` et `sort_order` pour l'affichage). **`release_date` / `release_precision`** (26/09/2026) : date de sortie de 70 séries — Fusion World : page produits officielle ; Masters : date « Available in tournaments » des cartes officielles et pages produits Bandai Asia ; Carddass Hondan : année ; Miracle Battle Carddass et Dragon Ball Heroes : année estimée (`annee_approx`). Sans date : promos Fusion World (FP), quelques réimpressions / promos Masters, DVD Number Card GT. `sort_order` reflète l'ordre chronologique réel de sortie de chaque extension — c'est cette colonne qui pilote l'ordre d'affichage du catalogue (le code de tri lui-même n'a pas changé, seule la donnée a été corrigée pour Fusion World le 23/08/2026).

### `cards` (115 lignes confirmées)
Le catalogue de référence. Colonnes clés : `game`, `game_slug` (FK → `games.slug`), `set_name`, `set_code`, `card_number`, `card_name`, `rarity`, `card_type`, `color`, `language`, `release_date`, `official_image_url`, `source_url`, `notes`, `review_status` (`confirmed` / `pending_review` / `rejected`), `review_source`.

Les cartes en `pending_review` proviennent d'une détection automatique (ex. reconnaissance sur dbzcollection.fr) et apparaissent dans l'onglet **Cartes à valider** avant d'intégrer le catalogue officiel. 0 carte en attente actuellement.

### `collection_items` (0 ligne — vide en prod actuellement)
Les cartes possédées ou en wishlist par un utilisateur. `status` = `owned` / `wishlist`. Champs : `card_id` (optionnel, FK → `cards.id`), `custom_name` (si la carte n'est pas cataloguée), `quantity`, `condition`, `language_override`, `grading_company`, `grading_score`, `price_paid`, `estimated_value`, `currency`, `acquired_date`, `notes`.

### `card_photos` (0 ligne)
Photos recto/verso liées à un `collection_items.id`, stockées dans le bucket Storage `card-photos` (accès via URL signée, 1h de validité).

### `hidden_cards` (17 lignes)
Table de jointure `user_id` + `card_id` : permet à un utilisateur de masquer une carte du catalogue sans la supprimer (utile si le catalogue contient une carte qui n'intéresse pas cet utilisateur). Réversible via "Afficher les cartes masquées".

## 5. Fonctionnalités (onglets de l'app)

**Charte graphique** (depuis le 24/09/2026) : « Sand, Teal, Gold & Navy », modes **nuit** et **jour**, **planifiés** : jour à 7 h, nuit à 20 h (bascule à l'heure pile, même app ouverte). Le bouton rond ☾ / ☀ toujours visible en haut de l'écran force l'autre mode jusqu'à la prochaine bascule (`localStorage["goku-theme-override"]`). Le numéro de version de l'app est affiché en bas du menu ☰ (écrit par `mobile/build.sh`). Les filtres **Jeu** (Collection, Wishlist, Catalogue) proposent toujours les 4 jeux. Détail, contrastes et jetons CSS : `docs/CHARTE.md`.

**Tri et regroupement** (depuis le 26/09/2026) : Catalogue, Ma collection et Wishlist ont un menu **Tri** (mémorisé par section) : *par jeu* (un en-tête par jeu avec son logo et son nombre de cartes, puis les séries dans l'ordre de sortie), *sorties récentes d'abord*, *sorties anciennes d'abord* (séries de tous les jeux mêlées par date, avec le nom court du jeu), et *ajout récent* (collection / wishlist). Chaque série affiche sa date de sortie (`game_sets.release_date`, précision `release_precision` : jour, mois, année ou « vers » + année estimée) ; dates inconnues en fin de liste. Les tuiles affichent le nom court du jeu (Masters, Fusion World, Carddass, DB Heroes).

**Navigation** (depuis le 23/09/2026) : menu burger ☰ en haut à gauche → tiroir latéral listant les 6 sections (avec le compteur de cartes à valider ; une pastille orange sur ☰ le signale menu fermé), l'e-mail du compte et **Déconnexion**. L'en-tête affiche le nom de la section courante, le bouton mode jour / nuit et un raccourci 📷 vers le scanner. Dans l'app Android, le bouton retour ferme le menu ou la fenêtre ouverte, sinon revient au tableau de bord, et ne quitte l'app que depuis celui-ci (plugin `@capacitor/app`).

1. **Tableau de bord** — statistiques : nombre de cartes possédées, quantité totale, valeur estimée, total dépensé, wishlist, taille du catalogue, répartition par jeu. La **valeur estimée** utilise la valeur saisie sur l'item, sinon le prix Cardmarket du jour × quantité (calcul en mémoire, jamais écrit dans `collection_items`) ; sous-titre « dont X € selon Cardmarket (N cartes) ».
2. **📷 Scanner & IA** — photo d'une carte (appareil photo ou galerie) → reconnaissance par le serveur IA local du Mac mini (voir `ai-server/README.md`) : cartes du catalogue correspondantes avec badge Possédée/Manquante, bouton **+ Ajouter** qui ouvre la fenêtre d'ajout pré-remplie avec la photo en recto. Plus une recherche en langage naturel (« mes cartes Masters en mauvais état »). Nécessite Tailscale actif sur l'appareil et le Mac mini allumé.
3. **Ma collection** — liste des cartes possédées (avec prix Cardmarket et lien quand la carte est liée), recherche, filtres (jeu, état), vérification rapide "est-ce que je possède déjà cette carte ?", ajout/édition avec photos recto/verso.
4. **Wishlist** — cartes souhaitées, recherche, prix Cardmarket et lien, lien **Vinted ↗** (recherche de la carte, ou de son nom personnalisé si elle est hors catalogue).
5. **Catalogue de référence** — toutes les cartes connues. Deux menus déroulants **Jeu** et **Série** (tous deux "tout sélectionné" par défaut) filtrent une grille plate de cartes (3 colonnes jusqu'à 480 px de large — téléphone, écran externe du Galaxy Z Fold —, 5 colonnes de 481 à 1100 px — écran interne déplié du Fold, petite tablette —, colonnes de ~220 px au-delà), triée par jeu puis par ordre chronologique d'extension (`game_sets.sort_order`) ; case à cocher pour afficher les cartes masquées. Chaque carte a un badge Possédée/Manquante, le **prix Cardmarket du jour** (infobulle : base du prix, date, « lien à vérifier » si correspondance `probable`) avec un lien **Cardmarket ↗**, un lien **Vinted ↗** sur les cartes manquantes, et un bouton Masquer/Réafficher.
6. **Cartes à valider** — file de modération pour les cartes détectées automatiquement (pas encore dans le catalogue officiel), avec boutons Valider / Rejeter.

## 6. Déploiement

> ⚠️ **Section historique — site abandonné le 23/09/2026 : projet Vercel `goku-ss3-collection` **mis en pause** (le site répond 503). L'app s'utilise désormais via l'**APK Android** (`mobile/`). Réactivable en un clic dans le dashboard Vercel si besoin.** Un `git push` sur `main` ne met plus rien en production ; pour livrer une modification de `index.html`, incrémenter `mobile/package.json` → `version` puis lancer `mobile/build.sh` et installer l'APK.

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
- **Passe base officielle Bandai (23/09/2026)** :
  - *Masters* : recherche des noms contenant « SS3 » / « Super Saiyan 3 » sur dbs-cardgame.com (51 résultats Goku, 29 numéros distincts) → les 29 étaient **déjà tous au catalogue**. Les variantes officielles (`_PR`, `_PR02`, `_BD`, `_SPR`) recoupent en grande partie les V.1/V.2/réimpressions Cardmarket déjà présentes ; non ajoutées faute de correspondance certaine.
  - *Fusion World* : les cartes s'appellent « Son Goku » sans la forme → revue visuelle des 373 illustrations Goku officielles (recto, verso des Leaders, parallèles) avec `ai-server/tools/find_fw_ss3.py`. **32 cartes ajoutées directement** (11 nouvelles dont 2 Leaders à face éveillée SS3 et 3 promos `FP`, + 21 versions parallèles numérotées `-P1`, `-P2`…) et **1 en « Cartes à valider »** (FB09-081, forme SS3 incertaine). Nouvelle série `Promotion Cards (FP)` dans `game_sets`. Images et fiches : base officielle Bandai (`review_source = 'bandai-officiel'`).
  - Le tri automatique par le modèle de vision local a été testé puis écarté (faux négatifs sur des SS3 évidents).
- **Passe Masters approfondie (26/09/2026)** : revue visuelle des 614 illustrations Goku officielles dont le nom ne dit pas la forme (`ai-server/tools/find_masters_ss3.py`) et comparaison image par image des variantes officielles des cartes « SS3 » avec le catalogue.
  - **7 cartes SS3 sans « SS3 » dans le nom** ajoutées : BT5-030, BT4-001 (Leader, face éveillée), BT10-098 et sa variante, BT12-031, DB3-053, EX13-03.
  - **6 variantes officielles** ajoutées (série `Promos`) : BT11-050_PR (Ultra Bout), BT11-127_PR (Judge), BT11-127_PR02 (Ultra Bout, illustration alternative), EB1-43_PR (« Winner »), BT22-135_PR (illustration alternative dorée), P-618_PR02 (→ `P-618-PR-V3`).
  - **À valider** : BT14-097 (Goku SS3 seulement en arrière-plan), SD2-02_PR (peut-être identique à SD2-02-ST-FOIL).
  - Déjà au catalogue : `_BD` = Reprints, BT6-029_PR = EX07, BT11-074_PR = TS01, SD10-02_PR = MB01 V.2, BT24-138_PR = God Rare, BT24-138_PR02 = AA, P-003_PR = Event Pack 2018, P-003_PR02 = Judge, BT22-135_PR02 = Unnumbered Promo.
  - Catalogue : **129 cartes confirmées** (68 Masters) + 2 à valider.
  - Limite de la veille quotidienne : elle ne détecte en Masters que les cartes dont le nom contient SS3 ; refaire cette passe visuelle à chaque nouvelle extension.
  - ⚠️ **FB05-119** (« Son Goku (V.1 - Secret Rare) », déjà au catalogue) : les 5 versions officielles montrent un Goku **SS1** sur Namek, pas SS3. Laissée en place, à trancher par l'utilisateur.
- **Ordre de tri des extensions Fusion World** : `game_sets.sort_order` mis à jour en base pour refléter l'ordre chronologique réel de sortie (du plus ancien — Awakened Pulse — au plus récent — Brightness of Hope). Le code de tri existait déjà et s'appuie sur cette colonne — seule la donnée a été corrigée.

## 8. Structure du fichier `index.html`

- `<head>` : meta, titre, favicon/apple-touch-icon/shortcut icon (`/logo.png?v=6`).
- `<style>` : variables CSS (`:root`), écran d'authentification, en-tête et menu latéral (burger), grilles de cartes (3 colonnes ≤ 480 px, 5 colonnes 481–1100 px), prix/liens Cardmarket et Vinted, section Scanner & IA, modale d'ajout/édition, toasts.
- `<body>` : écran d'authentification (connexion + réinitialisation par code), coquille de l'app (en-tête ☰ / titre / 📷, tiroir de menu, 6 panneaux), modale d'ajout/édition, conteneur de toasts.
- `<script>` : client PocketBase (`pbRequest`, `db`), auth (`doAuth`, `checkSession`), menu (`setMenuOpen`, bouton retour Android), chargement des données (`loadAll`, dont `loadMarketInfo`), cache des URLs de photos (`getPhotoUrl`), rendu des grilles (`renderGrid`, `renderCatalogueGrid`, `renderReviewGrid`, `cardTileHtml`), prix et liens (`marketHtml`, `marketPrice`, `vintedUrl`), Scanner & IA (`aiFetch`, `nativeAiRequest`, `shrinkPhoto`, `runScan`, `runAiSearch`), filtres, modale, upload de photos, utilitaires (`debounce`, `escapeHtml`, `gameDisplayName`).

## 9. Pistes pour la suite

- Continuer à enrichir le catalogue de référence (115 cartes au 23/09/2026) au fil des photos envoyées par l'utilisateur.
- Pas de pagination sur les grilles — à surveiller si le catalogue grossit beaucoup au-delà de quelques centaines de cartes.
- Un jeton expiré en cours de session n'est pas rafraîchi automatiquement (il l'est à chaque démarrage de l'app).
- 9 images Carddass/DBH orphelines identifiées mais non intégrées au catalogue (à confirmer avec l'utilisateur avant ajout).
- **À faire (utilisateur)** : définir le mot de passe du compte sur le Mac mini (`python3 ~/Services/goku/tools/set_password.py`), vérifier l'app, puis supprimer le projet Supabase fin octobre 2026 (et la clé `~/.config/goku-backup/secret`).
- **À trancher** : FB05-119 (au catalogue comme SS3, mais les 5 versions officielles montrent un Goku SS1) ; FB09-081 en « Cartes à valider » ; lien Cardmarket de BT20-095-V3 (prix ~5 800 €, correspondance `probable`).
- Lier à Cardmarket les 32 cartes Fusion World ajoutées le 23/09/2026 (parallèles, promos FP…) pour qu'elles aient un prix.

## 10. Période de test (à partir du 23/08/2026)

> Section historique : l'app est désormais livrée en APK Android (site Vercel abandonné le 23/09/2026).

Le projet entre dans une phase de test utilisateur de plusieurs semaines, sur l'app telle qu'elle est en production à cette date (logo correct, favicon fonctionnel, tri par jeu/extension chronologique, catalogue à 83 cartes).

- **Suivi des bugs :** utiliser l'onglet **Issues** du dépôt GitHub plutôt qu'une conversation isolée, pour garder un historique daté et consultable d'une session à l'autre.
- **Ce qui est considéré stable à ce stade :** authentification, catalogue de référence (affichage, filtres, tri), gestion de collection/wishlist (ajout, édition, photos), masquage de cartes, favicon/logo.
- **Ce qui n'a pas encore été testé en usage réel prolongé :** comportement au-delà de quelques centaines de cartes (pas de pagination), gestion d'un token de session expiré en cours d'usage (pas d'écoute `onAuthStateChange`), montée en charge du bucket Storage `card-photos`.

## 11. Prix Cardmarket (synchro quotidienne, depuis le 23/09/2026)

Source : fichiers **officiels et publics** de Cardmarket (pas de scraping), jeu n°13 = Dragon Ball Super (Masters **et** Fusion World) :
- catalogue : `https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_13.json`
- guide des prix : `https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_13.json` (régénéré par Cardmarket vers 02h50, heure de Paris)

Carddass et Dragon Ball Heroes ne sont pas vendus sur Cardmarket : pas de prix pour ces jeux.

### Fonctionnement (depuis le 28/09/2026 : Mac mini)
- Script `tools/cardmarket_sync.py` (Python standard), lancé **chaque jour à 05:15** par le LaunchAgent `com.goku.cardmarket` (installé par `deploy.sh`, journal `~/Services/goku/cardmarket.log`).
- Il télécharge les deux fichiers, garde le catalogue complet et les derniers prix dans une base locale `~/Services/goku/cardmarket.db`, puis écrit dans PocketBase : `card_market_info` (1 ligne par carte confirmée, champ JSON `info` avec `price_eur`, `price_basis`, `cardmarket_url`, `cardmarket_match`…, même calcul que l'ancienne vue Supabase — vérifié : 0 écart sur 130 cartes), `cardmarket_price_history` (un point par jour pour les produits liés) et `cardmarket_sync_log`.
- Lancer à la main : `python3 ~/Services/goku/tools/cardmarket_sync.py`.
- Avant le 28/09/2026 : fonction SQL `private.sync_cardmarket(13)` + pg_cron sur Supabase.
- La file de travail « produits Goku non liés » (ancienne vue `cardmarket_goku_review_queue`) se retrouve dans `cardmarket.db` (table `products`).

### Affichage dans l'app (depuis le 23/09/2026)
- `loadMarketInfo()` lit la collection `card_market_info` en parallèle du reste dans `loadAll()` → `marketInfo` (Map `card_id` → ligne). En cas d'erreur : simple `console.warn`, l'app se charge normalement sans prix.
- `marketHtml(cardId)` : badge prix vert + lien `Cardmarket ↗` (`target="_blank"`), utilisé dans les tuiles du Catalogue, de Ma collection / Wishlist et des résultats du Scanner. Rien n'est affiché pour les cartes sans prix ni lien (Carddass, DBH, cartes non liées).
- Tableau de bord : `estimated_value` de l'item, sinon `price_eur` de Cardmarket (`marketPrice(card_id)`).
- App Android : un lien `target="_blank"` ouvre bien le navigateur du téléphone (vérifié dans l'émulateur), rien de spécifique à Capacitor.
- Les 32 cartes Fusion World ajoutées le 23/09/2026 (parallèles, promos FP…) ne sont pas encore liées à un produit Cardmarket : pas de prix pour elles tant que `cards.cardmarket_id` n'est pas renseigné.

### Lien carte ↔ produit Cardmarket
- `cards.cardmarket_id` → `cardmarket_products.id_product`.
- `cards.cardmarket_match` : `sure` (candidat unique), `probable` (déduit de l'extension / de l'ordre des versions V.1/V.2/V.3), `verified` (validé à la main).
- 53 cartes liées au 23/09/2026. Le fichier Cardmarket ne donne ni le nom de l'extension ni la version (V.1, V.2…) : les liens `probable` sont à confirmer lors de la prochaine passe (en particulier **BT20-095-V3**, dont le prix ~5 800 € laisse penser à une version spéciale).
- Non liées : cartes Masters sans équivalent clair (P-003 et variantes, SD2-02-ST-FOIL, SD17, BT24-138 SCR/GDR, BT24-033-C FR/Collector, BT3-035…), et tout Carddass / DBH.

### Prochaine passe « SS3 manquantes »
Tous les produits dont le **nom** Cardmarket contient « SS3 / Super Saiyan 3 Son Goku » sont déjà au catalogue. Les manques restants sont des cartes dont le nom ne mentionne pas SS3 :
- Fusion World : ~137 numéros « Son Goku (FBxx-xxx) » non catalogués ;
- Masters : ~445 produits « Son Goku, … » sans « SS3 » dans le nom.
Il faut donc un contrôle **visuel** (image de la carte), par exemple via le serveur IA local (`ai-server/`), en partant de la vue `cardmarket_goku_review_queue`.

## 12. Sauvegardes (depuis le 23/09/2026 ; PocketBase depuis le 28/09/2026)

`backup/goku_backup.py` (Python standard) tourne sur le Mac mini **chaque jour à 09:30** (LaunchAgent `com.goku.backup`) et, si la dernière sauvegarde a plus de 7 jours :
- demande à PocketBase une **sauvegarde complète** (zip : base + images du catalogue + photos), la télécharge puis la supprime côté serveur ;
- exporte aussi en JSON lisible `collection_items`, `card_photos`, `hidden_cards`, `cards`, `games`, `game_sets` ;
- range le tout dans `iCloud Drive/Sauvegardes/Goku SS3/AAAA-MM-JJ/` (avec `manifest.json` et `LISEZMOI.txt` : restauration via l'admin PocketBase › Settings › Backups). Les **8** plus récentes sont gardées.
- Identifiants : superuser PocketBase dans `~/.config/goku-pb/superuser.json` (droits 600, jamais dans le dépôt).
- Installation : `backup/install.sh`. Sauvegarde immédiate : `python3 ~/.local/share/goku-backup/goku_backup.py --force`. Journal : `~/Library/Logs/goku-backup/backup.log`. Notification macOS en cas d'échec.
- Le « maintien en éveil » de Supabase n'existe plus (inutile).

## 13. Veille des nouvelles cartes Bandai et recherche Vinted (depuis le 23/09/2026)

### Veille quotidienne (`ai-server/tools/watch_bandai.py`)
LaunchAgent `com.goku.bandai-watch`, tous les jours à **08:00** sur le Mac mini (installé par `ai-server/install.sh`, journal `~/Library/Logs/goku-ai-server/bandai-watch.log`). Compare les bases officielles Bandai à la liste de ce qui a déjà été vu (`~/.local/share/goku-watch/seen.json`, initialisée le 23/09/2026 : 51 cartes Masters SS3, 373 illustrations Goku Fusion World) :
- **Masters** : nom officiel contenant SS3 / Super Saiyan 3 → nouvelle carte ajoutée **directement** (`review_source = 'bandai-veille'`) ; nouvelle variante officielle (`_PR`, `_SPR`…) → **Cartes à valider**.
- **Fusion World** : chaque nouvelle illustration Goku est examinée par le modèle de vision local ; écartée seulement s'il est sûr (≥ 0,9) d'une forme non dorée (base, Blue, God, UI, SS4), sinon → **Cartes à valider** (le modèle confond parfois SS3 et SS1).
- Séries inconnues créées dans `game_sets`. Notification macOS s'il y a du nouveau.
- Utilise la même clé secrète que la sauvegarde (`~/.config/goku-backup/secret`).
- Options : `--dry-run` (simulation), `--seed` (tout marquer comme vu).

### Recherche Vinted (`vintedUrl()` dans `index.html`)
Lien `https://www.vinted.fr/catalog?search_text=…` sur les cartes manquantes (catalogue, résultats du scanner) et la wishlist. Requête : numéro sans suffixe de rareté + « goku ss3 » (Masters) ou + « goku » (Fusion World) ; « carddass goku super saiyan 3 » ; « dragon ball heroes goku ss3 <n°> » ; nom personnalisé pour les items hors catalogue. Choix testés sur vinted.fr : le numéro seul et le filtre de catégorie « Cartes à collectionner » dégradent les résultats. Tri par pertinence.

## 14. Base de données sur le Mac mini (bascule du 28/09/2026)

- **PocketBase 0.40** (Homebrew), service launchd `com.goku.pocketbase` : `pocketbase serve --http=127.0.0.1:8092`, données dans `~/Services/goku/pb_data`. Accès distant **uniquement via Tailscale** : `tailscale serve --bg --tcp=8092 tcp://127.0.0.1:8092` → `http://100.109.190.30:8092` (tailnet seulement, pas de Funnel). Admin : `http://127.0.0.1:8092/_/`.
- **Déploiement** : `./deploy.sh` copie `backend/pb_migrations`, `backend/pb_hooks` et `tools/` vers `~/Services/goku` puis relance le service (les données ne sont jamais touchées) ; `--install` réinstalle les LaunchAgents (base + synchro Cardmarket).
- **Outils** (`tools/`) : `pb.py` (client Python superuser), `import_supabase.py` (copie Supabase → PocketBase, relançable), `cardmarket_sync.py`, `set_password.py`.
- **Import du 27/09/2026** : 4 jeux, 350 séries, 130 cartes (59 images rapatriées), 38 cartes de collection, 25 cartes masquées, 130 infos Cardmarket, 257 points d'historique ; tous les fichiers Supabase Storage archivés dans `~/Services/goku/supabase-archive/`. Le mot de passe n'a pas été repris : le définir avec `set_password.py`.
- **Serveur IA** (`ai-server/`) : vérifie le jeton PocketBase de l'utilisateur (`auth-refresh`) et lit catalogue / collection avec ce jeton (`PB_URL` dans `.env`). Il écoute désormais sur `127.0.0.1:8787` (Tailscale expose le port ; écouter sur 0.0.0.0 entrait en conflit avec `tailscale serve`).
- **Veille Bandai** : écrit dans PocketBase avec le compte superuser.
- **App** : `PB_URL` = `http://100.109.190.30:8092` dans l'APK ; dans un navigateur, l'origine si la page est servie sur le port 8092, sinon `http://127.0.0.1:8092`. `mobile/capacitor.config.json` autorise le contenu mixte (images HTTP du Mac mini dans la WebView HTTPS).
- **Supabase** : projet mis en pause, gardé 1 mois, puis à supprimer.

## 15. Illustrations (30/09/2026, v1.2)

- **Toutes les illustrations du catalogue sont hébergées sur le Mac mini** (champ `cards.image`) : les 71 images qui pointaient encore vers des sites externes (dbs-cardgame.com, dbscards.fr, dotgg, dbzcollection) ont été copiées. 5 images Cardmarket bloquées (403 : ST01-044, FB02-051, FS11-07, SB02-023, FB05-119) remplacées par les images officielles Bandai. `official_image_url` garde la source.
- La veille Bandai copie aussi l'illustration de chaque nouvelle carte (`Base.store_image` dans `watch_bandai.py`).
- **Photo par défaut** : une carte de la collection / wishlist sans photo perso affiche l'illustration du catalogue (tuiles et recto de la fenêtre d'ajout, mention « Illustration du catalogue »). Rien n'est téléversé : dès qu'une photo perso est ajoutée, elle la remplace.

