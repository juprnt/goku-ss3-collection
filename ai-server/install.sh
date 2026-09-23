#!/bin/zsh
# Installe (ou met à jour) le serveur IA comme service qui démarre avec le Mac.
# macOS interdit aux services launchd de lire iCloud Drive : on copie donc le serveur
# dans ~/.local/share/goku-ai-server/app et c'est cette copie qui tourne.
# À relancer après chaque modification du serveur.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
BASE="$HOME/.local/share/goku-ai-server"
APP="$BASE/app"
LABEL="com.goku.ai-server"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGS="$HOME/Library/Logs/goku-ai-server"

mkdir -p "$APP" "$LOGS"
rsync -a --delete --exclude .gitignore --exclude README.md --exclude install.sh \
  "$SRC/server.py" "$SRC/pyproject.toml" "$SRC/uv.lock" "$SRC/.env" "$SRC/run.sh" "$SRC/static" "$SRC/tools" "$APP/"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/zsh</string><string>$APP/run.sh</string></array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOGS/server.log</string>
  <key>StandardErrorPath</key><string>$LOGS/server.log</string>
</dict>
</plist>
EOF

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "gui/$(id -u)/$LABEL"
  while launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; do sleep 0.5; done
fi
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Serveur installé dans $APP — journaux : $LOGS/server.log"

# Veille quotidienne des nouvelles cartes Bandai (tools/watch_bandai.py), tous les jours à 08:00.
WATCH_LABEL="com.goku.bandai-watch"
WATCH_PLIST="$HOME/Library/LaunchAgents/$WATCH_LABEL.plist"
cat > "$WATCH_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$WATCH_LABEL</string>
  <key>WorkingDirectory</key><string>$APP</string>
  <key>ProgramArguments</key><array>
    <string>/opt/homebrew/bin/uv</string><string>run</string><string>--python</string><string>3.12</string>
    <string>python</string><string>tools/watch_bandai.py</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin</string>
    <key>UV_PROJECT_ENVIRONMENT</key><string>$BASE/venv</string>
  </dict>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$LOGS/bandai-watch.log</string>
  <key>StandardErrorPath</key><string>$LOGS/bandai-watch.log</string>
</dict>
</plist>
PLIST
if launchctl print "gui/$(id -u)/$WATCH_LABEL" >/dev/null 2>&1; then
  launchctl bootout "gui/$(id -u)/$WATCH_LABEL"
  while launchctl print "gui/$(id -u)/$WATCH_LABEL" >/dev/null 2>&1; do sleep 0.5; done
fi
launchctl bootstrap "gui/$(id -u)" "$WATCH_PLIST"
echo "Veille Bandai : tous les jours à 08:00 — journal : $LOGS/bandai-watch.log"
