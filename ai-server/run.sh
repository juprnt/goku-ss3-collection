#!/bin/zsh
# Lance le serveur IA. L'environnement Python est gardé hors d'iCloud pour ne pas le synchroniser.
cd "$(dirname "$0")"
export UV_PROJECT_ENVIRONMENT="$HOME/.local/share/goku-ai-server/venv"
exec uv run --python 3.12 python server.py
