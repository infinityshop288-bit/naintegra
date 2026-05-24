#!/usr/bin/env bash
# Empacota metadados + assets + projeto Android para Google AI Studio / Play Console.
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$MOBILE/.." && pwd)"
DIST="$MOBILE/dist/aistudio-export"
ZIP="$MOBILE/dist/naintegra-lex-aistudio.zip"

echo "==> Sincronizando web/lex"
bash "$MOBILE/scripts/sync-lex-www.sh"

echo "==> Preparando diretorio de exportacao"
rm -rf "$DIST"
mkdir -p "$DIST/assets"

cp "$MOBILE/aistudio/PROMPT.md" "$DIST/"
cp "$MOBILE/aistudio/PROMPT-COPIAR.txt" "$DIST/"
cp "$MOBILE/aistudio/GUIA-TELA-A-TELA.md" "$DIST/"
cp "$MOBILE/aistudio/PLAY-STORE-COPIAR.txt" "$DIST/"
cp "$MOBILE/aistudio/REFINAMENTOS-COPIAR.txt" "$DIST/"
cp "$MOBILE/aistudio/app-spec.json" "$DIST/"
cp "$MOBILE/store-assets/play-store.md" "$DIST/"
cp "$MOBILE/store-assets/google-ai-studio.md" "$DIST/"
cp "$MOBILE/store-assets/oauth-mobile.md" "$DIST/"
cp "$ROOT/web/site-root/.well-known/assetlinks.json" "$DIST/assetlinks.json"
cp "$MOBILE/aistudio/signing-fingerprints.json" "$DIST/"

if [[ -d "$MOBILE/store-assets/generated" ]]; then
  mkdir -p "$DIST/play-store-assets"
  cp -R "$MOBILE/store-assets/generated/." "$DIST/play-store-assets/"
  cp "$MOBILE/store-assets/release-notes-pt-BR.txt" "$DIST/"
  echo "Play Store assets incluidos"
fi

ICON=""
for candidate in \
  "$ROOT/web/lex/icons/icon-512.png" \
  "$MOBILE/android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png" \
  "$MOBILE/www/icons/icon-512.png"
do
  if [[ -f "$candidate" ]]; then
    ICON="$candidate"
    break
  fi
done

if [[ -n "$ICON" ]]; then
  cp "$ICON" "$DIST/assets/icon-512.png"
  echo "Icone: $ICON"
else
  echo "[AVISO] icon-512.png nao encontrado"
fi

cat > "$DIST/README.txt" <<'EOF'
NaIntegra Lex - exportacao Google AI Studio
==========================================

1. Abra https://aistudio.google.com/apps?source=start
2. Siga GUIA-TELA-A-TELA.md
3. Cole PROMPT-COPIAR.txt no Build an Android app
4. Anexe assets/icon-512.png
5. Teste no emulador -> Connect Play Console -> Internal Test Track
6. Upload capturas de play-store-assets/ na ficha da loja
7. Apos Internal Test: bash mobile/scripts/add-play-sha256.sh SHA256

Package: br.com.naintegracursos.lex
URL: https://www.naintegracursos.com.br/lex/
Asset links: https://www.naintegracursos.com.br/.well-known/assetlinks.json
EOF

echo "==> Empacotando projeto Capacitor Android"
STAGE="$MOBILE/dist/_cap_stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
if [[ -d "$MOBILE/android" ]]; then
  rsync -a \
    --exclude '.gradle' \
    --exclude 'build' \
    --exclude 'app/build' \
    --exclude 'local.properties' \
    --exclude '.idea' \
    "$MOBILE/android/" "$STAGE/android/"
  ( cd "$STAGE" && zip -rq "$DIST/capacitor-android.zip" android )
  echo "capacitor-android.zip criado"
else
  echo "[AVISO] mobile/android ausente"
fi
rm -rf "$STAGE"

echo "==> ZIP final"
mkdir -p "$MOBILE/dist"
rm -f "$ZIP"
( cd "$DIST" && zip -rq "$ZIP" . )
rm -rf "$DIST"

echo ""
echo "Pronto: $ZIP"
ls -lh "$ZIP"
