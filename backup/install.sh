#!/bin/zsh
# Installe (ou met à jour) le maintien en éveil + la sauvegarde hebdomadaire de Supabase.
# Le script est copié hors d'iCloud et lancé chaque jour à 09:30 par launchd (si le Mac dort
# à cette heure-là, il est lancé au réveil). À relancer après chaque modification.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/.local/share/goku-backup"
LABEL="com.goku.backup"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGS="$HOME/Library/Logs/goku-backup"
KEY="$HOME/.config/goku-backup/secret"

mkdir -p "$APP" "$LOGS" "$(dirname "$KEY")"
cp "$SRC/goku_backup.py" "$APP/"
[ -f "$KEY" ] || { touch "$KEY"; }
chmod 700 "$(dirname "$KEY")"; chmod 600 "$KEY"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/usr/bin/python3</string><string>$APP/goku_backup.py</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>30</integer></dict>
  <key>StandardOutPath</key><string>$LOGS/backup.log</string>
  <key>StandardErrorPath</key><string>$LOGS/backup.log</string>
</dict>
</plist>
PLIST

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "gui/$(id -u)/$LABEL"
  while launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; do sleep 0.5; done
fi
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installé : tous les jours à 09:30 — journal : $LOGS/backup.log"
[ -s "$KEY" ] || echo "⚠️  Il manque la clé secrète Supabase dans $KEY"
