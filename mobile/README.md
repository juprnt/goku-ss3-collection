# App Android (Capacitor)

L'app Android embarque le même `index.html` que le site Vercel, dans une WebView Capacitor
(`https://localhost`). Ce dossier est exclu du déploiement Vercel (`.vercelignore`).

## Construire l'APK

```bash
./build.sh   # -> ~/Developer/goku-ss3-mobile/GokuSS3-<version>.apk
```

La version vient du champ `version` de `package.json` (ex. `"0.2"`) : `build.sh` l'écrit
dans `versionName` et en déduit `versionCode` (0.2 → 200, 0.2.1 → 201). **Incrémenter la
version avant chaque nouvel APK distribué**, sinon Android refuse la mise à jour.

**Clé de signature** : Android n'installe une mise à jour que si l'APK est signé avec la même
clé que l'app déjà installée. `build.sh` vérifie que `~/.android/debug.keystore` est identique
à `mobile/signing.keystore` (copie gardée dans iCloud, même clé que PAPS IA) : il la remet en
place si elle manque et s'arrête si elle diffère. Ce fichier est **exclu de git**
(`mobile/.gitignore`) car le dépôt GitHub est public : ne jamais le committer.

Prérequis (installés via Homebrew) : `node`, `openjdk@21`, cask `android-commandlinetools`
avec `platform-tools`, `platforms;android-36`, `build-tools;36.0.0`.

Le projet Capacitor (node_modules, `android/`, builds Gradle) est généré dans
`~/Developer/goku-ss3-mobile`, hors d'iCloud. Le dépôt ne garde que `package.json`,
`capacitor.config.json` et `build.sh`, qui à chaque build :

1. copie `index.html` et `logo.png` dans `www/` ;
2. remplace le SDK Supabase du CDN unpkg par une copie embarquée (`www/supabase.js`, même
   version) pour que l'app démarre même si le réseau n'est pas encore prêt ;
3. ajoute la permission `CAMERA` (scanner) et génère l'icône à partir de `logo.png` ;
4. `cap sync` puis `gradlew assembleDebug`.

**Refaire un build après chaque modification de `index.html`** : contrairement au site,
l'app n'est pas mise à jour automatiquement.

## Différences avec le site

- Détection via `IS_NATIVE_APP` dans `index.html`.
- Les appels au serveur IA passent par `CapacitorHttp` (client HTTP natif Android) : pas de
  CORS ni de blocage « réseau privé » du navigateur. La photo est envoyée en base64 à
  `/identify/base64`.
- Le lien « Mot de passe oublié » renvoie vers le site Vercel (l'origine `https://localhost`
  de l'app n'est pas joignable depuis un email).

## Tester dans un émulateur

```bash
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
$ANDROID_HOME/emulator/emulator -avd goku-test -no-window -no-audio
$ANDROID_HOME/platform-tools/adb install -r ~/Developer/goku-ss3-mobile/GokuSS3.apk
```

Éviter `adb shell am force-stop` : sur ce Mac, `adb` (platform-tools 37) plante quand une app
déboguable est tuée.
