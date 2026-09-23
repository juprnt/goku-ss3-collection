#!/bin/zsh
# Construit l'APK Android de Goku SS3 à partir de ../index.html et ../logo.png.
# Le projet Capacitor (node_modules, android/, builds Gradle) vit hors d'iCloud, dans
# ~/Developer/goku-ss3-mobile, pour ne pas synchroniser des milliers de fichiers.
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WS="$HOME/Developer/goku-ss3-mobile"
export JAVA_HOME=/opt/homebrew/opt/openjdk@21
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
export PATH="$JAVA_HOME/bin:/opt/homebrew/bin:$PATH"

mkdir -p "$WS/www" "$WS/assets"
cp "$REPO/mobile/package.json" "$REPO/mobile/capacitor.config.json" "$WS/"
cp "$REPO/index.html" "$REPO/logo.png" "$WS/www/"
cd "$WS"
npm install --no-audit --no-fund --loglevel=error

# SDK Supabase embarqué dans l'APK (même version que le CDN d'index.html) : l'app ne dépend
# plus d'unpkg au démarrage, qui peut échouer si le réseau n'est pas encore prêt.
cp node_modules/@supabase/supabase-js/dist/umd/supabase.js www/supabase.js
perl -pi -e 's#https://unpkg.com/\@supabase/supabase-js\@[0-9.]+#supabase.js#' www/index.html
grep -q '<script src="supabase.js">' www/index.html || { echo "Remplacement du SDK Supabase échoué"; exit 1; }

[ -d android ] || npx cap add android

# Appareil photo pour le scanner (champ <input capture>).
MANIFEST=android/app/src/main/AndroidManifest.xml
grep -q 'android.permission.CAMERA' "$MANIFEST" || \
  perl -0pi -e 's#</manifest>#    <uses-permission android:name="android.permission.CAMERA" />\n</manifest>#' "$MANIFEST"

# Icône : le logo (120 px) agrandi en 1024 px, sur le fond sombre de l'app.
sips -z 1024 1024 "$REPO/logo.png" --out assets/icon.png >/dev/null
npx capacitor-assets generate --android --iconBackgroundColor '#0f1115' --iconBackgroundColorDark '#0f1115' \
  --splashBackgroundColor '#0f1115' --splashBackgroundColorDark '#0f1115' >/dev/null

npx cap sync android
(cd android && ./gradlew assembleDebug -q)
cp android/app/build/outputs/apk/debug/app-debug.apk "$WS/GokuSS3.apk"
echo "APK prêt : $WS/GokuSS3.apk"
