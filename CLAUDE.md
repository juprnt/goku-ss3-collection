# Goku SS3 Collection — notes pour Claude Code

- Lire `README.md` puis `DOCUMENTATION.md` avant toute modification.
- App = un seul fichier `index.html` (vanilla JS, pas de build). Backend Supabase (projet `vtdohksscretlbvhsgfo`).
- Le site Vercel est **abandonné** (projet en pause depuis le 23/09/2026) : l'app est livrée en APK via `mobile/build.sh` (incrémenter `version` dans `mobile/package.json`). Demander confirmation avant de pousser sur GitHub (dépôt public).
- Ne jamais toucher `collection_items` / `card_photos` sans action explicite de l'utilisateur (données perso).
- Tâches préparées en attente : voir `docs/` (ex. `docs/TASK-prix-cardmarket.md`).
