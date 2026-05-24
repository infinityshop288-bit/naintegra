#!/usr/bin/env bash
# Ícones e splash NaIntegra Lex → Android + iOS (Capacitor).
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$MOBILE/.." && pwd)"
ICON="$ROOT/web/lex/icons/icon-512.png"

if [[ ! -f "$ICON" ]]; then
  echo "Ícone não encontrado: $ICON" >&2
  exit 1
fi

echo "==> Ícones Android"
ANDROID_RES="$MOBILE/android/app/src/main/res"
apply_icon() {
  local dir="$1" px="$2"
  mkdir -p "$ANDROID_RES/$dir"
  sips -z "$px" "$px" "$ICON" --out "$ANDROID_RES/$dir/ic_launcher.png" >/dev/null
  cp "$ANDROID_RES/$dir/ic_launcher.png" "$ANDROID_RES/$dir/ic_launcher_round.png"
  sips -z "$px" "$px" "$ICON" --out "$ANDROID_RES/$dir/ic_launcher_foreground.png" >/dev/null
}
apply_icon mipmap-mdpi 48
apply_icon mipmap-hdpi 72
apply_icon mipmap-xhdpi 96
apply_icon mipmap-xxhdpi 144
apply_icon mipmap-xxxhdpi 192

echo "==> Splash Android"
mkdir -p "$MOBILE/android/app/src/main/res/drawable"
sips -z 480 480 "$ICON" --out "$MOBILE/android/app/src/main/res/drawable/splash.png" >/dev/null

if [[ -d "$MOBILE/ios/App/App/Assets.xcassets/AppIcon.appiconset" ]]; then
  echo "==> Ícones iOS"
  IOS_ICON="$MOBILE/ios/App/App/Assets.xcassets/AppIcon.appiconset"
  sips -z 1024 1024 "$ICON" --out "$IOS_ICON/AppIcon-1024.png" >/dev/null
  cat > "$IOS_ICON/Contents.json" <<'JSON'
{
  "images": [
    { "filename": "AppIcon-1024.png", "idiom": "universal", "platform": "ios", "size": "1024x1024" }
  ],
  "info": { "author": "xcode", "version": 1 }
}
JSON
fi

echo "Branding aplicado."
