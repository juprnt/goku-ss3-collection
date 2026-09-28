#!/bin/zsh
# Déploie la base Goku SS3 (PocketBase) sur le Mac mini, comme Mariage & Baptême :
# copie migrations / hooks / outils vers ~/Services/goku (hors iCloud) et relance le service launchd.
# Les données (~/Services/goku/pb_data) ne sont jamais touchées.
set -e
SRC="${0:A:h}"
DEST="$HOME/Services/goku"
mkdir -p "$DEST"/{pb_data,pb_public,pb_migrations,pb_hooks,tools}
rsync -a --delete --exclude '.DS_Store' "$SRC/backend/pb_migrations/" "$DEST/pb_migrations/"
rsync -a --delete --exclude '.DS_Store' "$SRC/backend/pb_hooks/" "$DEST/pb_hooks/"
rsync -a --delete --exclude '.DS_Store' --exclude '__pycache__' "$SRC/tools/" "$DEST/tools/"

PLIST="$HOME/Library/LaunchAgents/com.goku.pocketbase.plist"
if [[ "$1" == "--install" || ! -f "$PLIST" ]]; then
  sed "s|__HOME__|$HOME|g" "$SRC/backend/com.goku.pocketbase.plist" > "$PLIST"
  launchctl bootout "gui/$(id -u)/com.goku.pocketbase" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
else
  launchctl kickstart -k "gui/$(id -u)/com.goku.pocketbase"
fi
# Synchro Cardmarket chaque nuit (tools/cardmarket_sync.py, 05:15).
CPLIST="$HOME/Library/LaunchAgents/com.goku.cardmarket.plist"
if [[ -f "$SRC/backend/com.goku.cardmarket.plist" ]] && [[ "$1" == "--install" || ! -f "$CPLIST" ]]; then
  sed "s|__HOME__|$HOME|g" "$SRC/backend/com.goku.cardmarket.plist" > "$CPLIST"
  launchctl bootout "gui/$(id -u)/com.goku.cardmarket" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$CPLIST"
fi
echo "Base déployée : http://127.0.0.1:8092 (admin : http://127.0.0.1:8092/_/)"
