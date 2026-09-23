# Serveur IA local (Mac mini)

Petit serveur FastAPI qui tourne sur le Mac mini à côté d'Ollama et expose l'IA à l'app
Goku SS3 (web aujourd'hui, Android ensuite). Ce dossier est exclu du déploiement Vercel
(`.vercelignore` à la racine).

## Lancer

```bash
cp .env.example .env   # puis renseigner SUPABASE_ANON_KEY (la même que dans index.html)
./install.sh           # installe/met à jour le service qui démarre avec le Mac
```

`install.sh` copie le serveur dans `~/.local/share/goku-ai-server/app` (macOS interdit aux
services launchd de lire iCloud Drive) et l'enregistre comme LaunchAgent
`com.goku.ai-server` (redémarrage automatique). **À relancer après chaque modification.**
Journaux : `~/Library/Logs/goku-ai-server/server.log`. Pour un lancement ponctuel au premier
plan : `./run.sh`.

Ollama tourne lui aussi comme service : `brew services start ollama`.

## Accès depuis le téléphone (Tailscale)

Le serveur est exposé en HTTPS sur le réseau privé Tailscale :

```bash
/Applications/Tailscale.app/Contents/MacOS/Tailscale serve --bg --https=443 http://127.0.0.1:8787
```

→ `https://macmini-de-juli1.tail13a987.ts.net` (joignable uniquement par les appareils du
tailnet). C'est cette adresse qu'utilise l'onglet **📷 Scanner & IA** de l'app
(`AI_SERVER_URL` dans `index.html`). Le HTTPS est indispensable : l'app étant servie en
HTTPS, le navigateur bloquerait un appel vers `http://`. `allow_private_network=True` dans
la config CORS répond au contrôle *Private Network Access* de Chrome.

Prérequis : `uv` (`brew install uv`) et Ollama avec le modèle `OLLAMA_MODEL` (vision requise).
L'environnement Python est créé dans `~/.local/share/goku-ai-server/venv`, hors d'iCloud.

## Endpoints

Tous (sauf `/health` et `/`) exigent `Authorization: Bearer <jeton Supabase de l'utilisateur>`.
Le serveur n'a **aucune clé service_role** : il lit Supabase avec le jeton de l'utilisateur,
donc les policies RLS s'appliquent comme dans l'app.

| Méthode | Route       | Entrée                         | Sortie |
|---------|-------------|--------------------------------|--------|
| GET     | `/health`   | —                              | état d'Ollama / du modèle |
| GET     | `/`         | —                              | page de test (connexion, photo, recherche) |
| POST    | `/identify` | `multipart/form-data`, champ `photo` | infos lues sur la carte, 5 candidats du catalogue avec score et statut possédée/wishlist, `best_match_id` si correspondance nette |
| POST    | `/search`   | `{"query": "..."}`             | filtres compris par l'IA + résultats (collection, wishlist, catalogue ou cartes manquantes) |

## Fonctionnement

- **Identification** : le modèle de vision lit la carte (jeu, numéro, nom, rareté...), puis
  le serveur compare ces infos au catalogue confirmé (numéro exact = +60, extension = +15,
  jeu = +10, similarité du nom jusqu'à +20, rareté = +5). `best_match_id` n'est renseigné
  que si le meilleur score ≥ 60 avec au moins 15 points d'avance.
- **Recherche** : le modèle traduit la question en filtres JSON, appliqués ensuite en Python
  sur les données Supabase — l'IA ne voit jamais les données elles-mêmes.
- Les modèles MLX ne gèrent pas la sortie structurée d'Ollama : le serveur bascule
  automatiquement sur un schéma décrit dans le prompt et ré-valide la réponse.

Temps mesurés sur Mac mini M6 / `qwen3.6:35b-mlx` : ~11 s pour une identification (modèle
déjà chargé), ~2,5 s pour une recherche.
