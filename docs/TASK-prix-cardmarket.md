# Tâche : afficher le prix Cardmarket et un lien cliquable sur les cartes

_Préparée le 23/09/2026. Toute la partie base de données est déjà faite et en production. Il ne reste que le front (`index.html`)._

## Objectif
1. Sur chaque carte du **Catalogue de référence** (`cardTileHtml`), afficher le prix Cardmarket du jour et un lien « Voir sur Cardmarket ».
2. Faire de même sur les tuiles **Ma collection** / **Wishlist** (`renderGrid`) quand l'item est lié à une carte du catalogue (`item.cards`).
3. Tableau de bord (`renderDashboard`) : quand `estimated_value` est vide pour une carte possédée, utiliser le prix Cardmarket pour la « Valeur estimée » (ne **jamais** écrire dans `collection_items`, calcul en mémoire uniquement).

## Source de données : vue `public.card_market_info`
Une ligne par carte confirmée (83). Lecture autorisée pour `authenticated` (RLS via `security_invoker`), refusée à `anon`.

| Colonne | Type | Sens |
|---|---|---|
| `card_id` | uuid | = `cards.id` |
| `price_eur` | numeric \| null | prix à afficher, déjà choisi côté SQL (null si pas de prix) |
| `price_basis` | text \| null | ce que représente `price_eur` : `tendance`, `tendance foil`, `moyenne 30 j`, `moyenne 30 j foil`, `à partir de`, `à partir de (foil)` |
| `price_date` | date | date du guide des prix Cardmarket |
| `cardmarket_url` | text \| null | lien à ouvrir (page produit ou recherche Cardmarket) |
| `cardmarket_match` | text \| null | `sure` / `probable` / `verified` : fiabilité du lien carte ↔ produit |
| `trend`, `avg30`, `low`, `trend_foil`, `avg30_foil`, `low_foil` | numeric | détails si besoin (infobulle) |
| `cardmarket_id`, `cardmarket_name` | int / text | produit Cardmarket lié |

État au 23/09 : 52 cartes avec prix, 53 avec lien. Carddass et Dragon Ball Heroes n'ont ni prix ni lien (pas vendus sur Cardmarket) — c'est normal, ne rien afficher.

Mise à jour : automatique chaque jour (pg_cron `cardmarket-daily-sync`, 05:15 UTC). Rien à faire côté front.

## Implémentation suggérée (vanilla JS, pas de build, garder le style existant)
1. Variable globale à côté de `cardsCatalogue` (~ligne 482) :
   ```js
   let marketInfo = new Map(); // card_id -> ligne de card_market_info
   ```
2. Nouvelle fonction chargée en parallèle dans `loadAll()` (ajouter au `Promise.all`) :
   ```js
   async function loadMarketInfo() {
     const { data, error } = await sb.from("card_market_info").select("*");
     if (error) { console.warn("Prix Cardmarket indisponibles:", error.message); return; } // non bloquant
     marketInfo = new Map((data || []).map(r => [r.card_id, r]));
   }
   ```
   Une erreur ici ne doit **pas** afficher de toast bloquant ni casser le reste du chargement.
3. Helper de rendu partagé :
   ```js
   function marketHtml(cardId) {
     const m = marketInfo.get(cardId);
     if (!m) return "";
     const price = m.price_eur != null
       ? `<span class="tag price" title="${escapeHtml(m.price_basis || "")} · Cardmarket ${m.price_date || ""}${m.cardmarket_match === "probable" ? " · lien à vérifier" : ""}">${Number(m.price_eur).toFixed(2)} €</span>`
       : "";
     const link = m.cardmarket_url
       ? `<a class="cm-link" href="${escapeHtml(m.cardmarket_url)}" target="_blank" rel="noopener noreferrer">Cardmarket ↗</a>`
       : "";
     return price || link ? `<div class="market">${price}${link}</div>` : "";
   }
   ```
   - Insérer `${marketHtml(c.id)}` dans `cardTileHtml` (sous `.tags`), et `${item.cards ? marketHtml(item.cards.id) : ""}` dans `renderGrid`.
   - Vérifier que `item.cards` contient bien `id` (voir la requête de `loadCollection`, ~ligne 650) ; sinon utiliser `item.card_id`.
   - Le clic sur le lien ne doit pas déclencher d'autre action de la tuile (`event.stopPropagation()` si la tuile devient cliquable).
4. CSS : petit style discret pour `.market`, `.tag.price` (ex. couleur verte comme `#stat-value`) et `.cm-link`, lisible sur mobile (grille 3-4 cartes par ligne, cf. commit ff8f6a6) — pas de débordement horizontal.
5. `renderDashboard` : pour chaque item possédé,
   `valeur = Number(i.estimated_value) || marketInfo.get(i.card_id)?.price_eur || 0`, multiplié par la quantité. Optionnel : sous-titre « dont X € selon Cardmarket ».
6. Ne pas oublier l'app Android : `mobile/build.sh` régénère l'APK depuis `index.html`, donc rien de spécial, mais tester que `target="_blank"` ouvre bien le navigateur dans Capacitor (sinon utiliser `window.open(url, "_system")`).

## Contraintes du projet (rappel)
- Tout est dans `index.html` (HTML + CSS + JS inline), pas de modules ES, pas de bundler.
- Échapper tout texte venant de la base avec `escapeHtml`.
- Ne jamais modifier `collection_items` / `card_photos` sans action explicite de l'utilisateur.
- `git push` sur `main` = déploiement **direct en production** (Vercel). Tester en local d'abord (ouvrir `index.html` avec un petit serveur, ex. `python3 -m http.server`) et demander à Ju avant de pousser.
- Mettre à jour `DOCUMENTATION.md` (§5 Fonctionnalités, §11 Prix Cardmarket) une fois fait.

## Vérification attendue
- `node --check` sur le JS extrait, ou chargement dans un navigateur sans erreur console.
- Une carte Masters liée (ex. **EB1-043-SR**) affiche un prix et un lien qui ouvre Cardmarket.
- Une carte Fusion World (ex. **FB02-051**) : lien vers la recherche Cardmarket par numéro.
- Une carte Carddass : ni prix ni lien, et aucune erreur.
- Si la vue est inaccessible (tester en renommant temporairement la vue dans le code), l'app se charge quand même.
