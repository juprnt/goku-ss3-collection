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

# Clé de signature : Android n'accepte une mise à jour (en gardant la session et les données
# de l'app) que si le nouvel APK est signé avec la même clé. Gradle signe avec
# ~/.android/debug.keystore ; on en garde une copie ici (iCloud, même clé que PAPS IA) et on
# la remet en place si elle manque (nouveau Mac, dossier effacé). Si les deux diffèrent, on
# s'arrête : l'APK obligerait à désinstaller l'app.
# La copie n'est PAS versionnée (mobile/.gitignore) : le dépôt GitHub est public.
KEYSTORE="$HOME/.android/debug.keystore"
if [ ! -f "$REPO/mobile/signing.keystore" ]; then
  echo "mobile/signing.keystore manquant (copie iCloud de la clé de signature). Le recopier depuis PAPS IA/mobile/."
  exit 1
elif [ ! -f "$KEYSTORE" ]; then
  mkdir -p "$HOME/.android" && cp "$REPO/mobile/signing.keystore" "$KEYSTORE"
elif ! cmp -s "$KEYSTORE" "$REPO/mobile/signing.keystore"; then
  echo "~/.android/debug.keystore diffère de mobile/signing.keystore : l'APK ne pourrait pas mettre à jour l'app installée."
  echo "Restaurer la clé : cp \"$REPO/mobile/signing.keystore\" \"$KEYSTORE\""
  exit 1
fi

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

# HTTP autorisé uniquement vers l'IP Tailscale du Mac mini (serveur IA, voir AI_SERVER_URL).
mkdir -p android/app/src/main/res/xml
cat > android/app/src/main/res/xml/network_security_config.xml <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">100.109.190.30</domain>
    </domain-config>
</network-security-config>
XML
grep -q 'networkSecurityConfig' "$MANIFEST" || perl -0pi -e 's#<application#<application android:networkSecurityConfig="\@xml/network_security_config"#' "$MANIFEST"

# Icône : le logo (120 px) agrandi en 1024 px, sur le fond sombre de l'app.
sips -z 1024 1024 "$REPO/logo.png" --out assets/icon.png >/dev/null
npx capacitor-assets generate --android --iconBackgroundColor '#0f1115' --iconBackgroundColorDark '#0f1115' \
  --splashBackgroundColor '#0f1115' --splashBackgroundColorDark '#0f1115' >/dev/null

# Version de l'app = champ "version" de mobile/package.json (ex. "0.2").
# versionCode doit augmenter à chaque version pour qu'Android accepte la mise à jour :
# 0.2 -> 200, 0.2.1 -> 201, 1.3 -> 10300.
VERSION=$(node -p "require('./package.json').version")
IFS=. read -r V_MAJ V_MIN V_PAT <<< "$VERSION"
VERSION_CODE=$(( ${V_MAJ:-0} * 10000 + ${V_MIN:-0} * 100 + ${V_PAT:-0} ))
perl -pi -e "s/versionCode \d+/versionCode $VERSION_CODE/; s/versionName \"[^\"]*\"/versionName \"$VERSION\"/" android/app/build.gradle

npx cap sync android
(cd android && ./gradlew assembleDebug -q)
APK="$WS/GokuSS3-$VERSION.apk"
rm -f "$WS"/GokuSS3-*.apk   # ne garder que la dernière version
cp android/app/build/outputs/apk/debug/app-debug.apk "$APK"
echo "APK prêt : $APK (version $VERSION, code $VERSION_CODE)"
