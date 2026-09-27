# Charte graphique Goku SS3 Collection — « Combo 27 · Sand, Teal, Gold & Navy »

Adoptée le 24/09/2026. Remplace l'ancien thème sombre unique (fond `#0F1115`, accent orange
`#FF7A1A`). Appliquée dans `index.html` (jetons CSS en tête de `<style>`) et l'icône / l'écran de
lancement Android (`mobile/build.sh`, `mobile/capacitor.config.json`). Deux modes : **nuit** et
**jour**, planifiés : jour à 7 h, nuit à 20 h ; le bouton rond ☾ / ☀ toujours visible en haut de l'écran force l'autre mode jusqu'à la prochaine bascule.

## 1. Palette

| Nom | HEX | Rôle |
|---|---|---|
| **Navy** | `#083A4F` | Fond du mode nuit ; texte du mode jour ; fond de l'icône |
| **Sand** | `#E5E1DD` | Fond du mode jour ; texte du mode nuit |
| **Teal** | `#407E8C` | Identité : titres de blocs, élément actif du menu, liens, focus |
| **Or clair** | `#E4B448` | Action en mode nuit (boutons principaux, meilleure correspondance) |
| **Or foncé** | `#9C600C` | Action en mode jour |
| Blanc | `#FFFFFF` | Cartes du mode jour ; texte sur l'Or foncé |

**L'or.** Le combo proposait `#A58D66`. On garde l'or déjà présent : celui du **logo** (badge
« EDITION »), dont on prend la lumière `#E4B448` et l'ombre `#9C600C`. Le `#A58D66` du combo est
trop terne pour une action (3,8:1 sur Navy, 3,2:1 avec du texte blanc) ; les deux ors du logo
tiennent 6,3:1 (Navy sur Or clair) et 5,1:1 (blanc sur Or foncé). Deux versions parce qu'aucune
teinte ne marche sur les deux fonds : l'Or clair disparaît sur Sand, l'Or foncé est terne sur Navy.
L'ancien orange `#FF7A1A` disparaît : il concurrençait l'or du logo.

**Teintes dérivées** (calculées pour tenir les contrastes) :

| Nom | HEX | Pourquoi |
|---|---|---|
| Teal clair | `#A0BEC6` | Teal pur sur Navy = 2,7:1, illisible en texte la nuit |
| Teal foncé | `#2F6A7A` | Teal pur sur Sand = 3,5:1, insuffisant le jour |
| Cartes nuit | `#114155`, bordures `#245468` | Navy éclairci : l'élévation se lit par la clarté |
| Champs / tiroir nuit | `#062C3B` | Navy assombri : les zones de saisie se creusent |
| Cartes jour | `#FFFFFF`, champs `#F7F5F3`, bordures `#D6D0C9` | Les cartes blanches « flottent » sur Sand |

**Couleurs d'état** (hors palette, indispensables à une app de collection) :

| État | Nuit | Jour | Usage |
|---|---|---|---|
| Succès | `#5FD08F` | `#1B6E44` | Badge « Possédée », prix Cardmarket, messages de réussite |
| Alerte | `#FF9B8C` | `#B3261E` | Badge « Manquante », erreurs, bouton Supprimer |

## 2. Règle 60 / 30 / 10

| Part | Mode nuit | Mode jour |
|---|---|---|
| **60 %** — surfaces | Navy + cartes `#114155` | Sand + cartes blanches |
| **30 %** — identité | Teal clair (titres de blocs, liens Cardmarket / Vinted, élément actif), aplat Teal 16 % | Teal foncé, aplat `#D9E5E8` |
| **10 %** — action | Or clair plein, texte Navy | Or foncé plein, texte blanc |
| Texte | Sand, `#AAB5B8` (secondaire) | Navy, `#466977` (secondaire) |

Les **illustrations des cartes** restent les vraies couleurs de la collection : l'interface, sobre
(Navy / Sand / Teal), leur laisse la vedette. L'or est réservé à ce qui se touche : « + Ajouter »,
« Enregistrer », « Prendre une photo », et au cadre de la meilleure correspondance du scanner.
Une seule action dorée par zone ; les actions secondaires sont en contour neutre.

## 3. Contrastes (WCAG 2.2)

Seuils : 4,5:1 texte courant (AA), 3:1 grands textes et composants.

| Combinaison | Ratio | Usage |
|---|---|---|
| Sand sur Navy / sur carte nuit | **9,3 / 7,9:1** | Texte courant nuit (AAA) |
| `#AAB5B8` sur carte nuit | **4,9:1** | Texte secondaire nuit |
| Teal clair sur Navy / sur carte | **6,2 / 5,2:1** | Accents, liens nuit |
| Navy sur Or clair | **6,3:1** | Boutons nuit |
| Succès / Alerte sur carte nuit | **5,3 / 5,0:1** | Badges nuit |
| Navy sur Sand / sur blanc | **9,3 / 12,1:1** | Texte courant jour (AAA) |
| `#466977` sur Sand | **4,6:1** | Texte secondaire jour |
| Teal foncé sur Sand | **4,7:1** | Accents, liens jour |
| Blanc sur Or foncé (survol `#89540B`) | **5,1 (6,3):1** | Boutons jour |
| Succès / Alerte jour sur leur teinte | **5,3 / 5,4:1** | Badges jour |
| ❌ Teal pur sur Navy | 2,7:1 | → Teal clair |
| ❌ Or clair sur Sand | 1,4:1 | Jamais de jour → Or foncé |
| ❌ Or foncé sur Sand (texte) | 4,0:1 | Or foncé en aplat seulement |

## 4. Règles d'usage

- Toujours passer par les jetons CSS (`--bg`, `--card`, `--text`, `--accent`, `--cta`,
  `--success`, `--danger`…), jamais de HEX en dur : ils basculent seuls entre nuit et jour.
- Texte sur Or clair : Navy. Texte sur Or foncé : blanc. Au survol, l'Or clair s'éclaircit, l'Or
  foncé s'assombrit (éclaircir ferait passer le blanc sous 4,5:1).
- L'or n'est ni une couleur de titre, ni un fond de section. Succès et alerte ne servent qu'aux
  états, jamais à la décoration.
- Liens Cardmarket et Vinted : même couleur d'accent (le libellé suffit à les distinguer).

## 5. Jetons CSS (`index.html`)

| Jeton | Nuit | Jour |
|---|---|---|
| `--bg`, `--bg-glow` | Navy, `#174659` | Sand, `#F3F0ED` |
| `--bg-alt` (champs, tiroir, lignes) | `#062C3B` | `#F7F5F3` |
| `--card`, `--border` | `#114155`, `#245468` | `#FFFFFF`, `#D6D0C9` |
| `--text`, `--text-dim` | Sand, `#AAB5B8` | Navy, `#466977` |
| `--accent`, `--accent-dim`, `--brand-line` | `#A0BEC6`, Teal 16 %, `#A0BEC6` | `#2F6A7A`, `#D9E5E8`, Teal |
| `--cta`, `--cta-ink`, `--cta-hover` | Or clair, Navy, `#E9C36D` | Or foncé, blanc, `#89540B` |
| `--success`, `--danger` | `#5FD08F`, `#FF9B8C` | `#1B6E44`, `#B3261E` |
| `--topbar-bg` | Navy 92 % | Sand 92 % |

Thème : attribut `data-theme="light"` sur `<html>`, posé avant l'affichage (script dans `<head>`)
d'après l'heure (`scheduledTheme` : 7 h → 20 h = jour), sauf forçage manuel en cours (`localStorage["goku-theme-override"]`, valable jusqu'à la prochaine bascule). Bascule : bouton rond `.theme-toggle` (lune la nuit,
soleil le jour) dans l'en-tête — collé en haut, donc visible dans toutes les sections — et en haut à
droite de l'écran de connexion ; entrée en doublon dans le pied du menu ☰.

## 6. Typographie

Police système (`-apple-system`, Roboto sur Android) : lisible en très petit sur les tuiles à 3 et 5
colonnes du Z Fold. Titres en 700, texte courant 400-600, étiquettes 10-12 px en 600.

## 7. Logo et icône

Logo inchangé (silhouette de Goku sur or). Icône et écran de lancement sur fond **Navy** : l'or du
logo y ressort mieux que sur l'ancien noir.
