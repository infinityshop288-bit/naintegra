#!/usr/bin/env bash
# Pipeline completo: sync → cap → signing → assetlinks → export AI Studio → smoke test.
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$MOBILE/.." && pwd)"
export RUBYOPT="-rlogger ${RUBYOPT:-}"

echo "==> 1/6 Preparar projetos nativos"
bash "$MOBILE/scripts/prepare-native-projects.sh"

echo ""
echo "==> 2/6 Assinatura + assetlinks.json"
bash "$MOBILE/scripts/setup-android-signing.sh"

echo ""
echo "==> 3/6 Export AI Studio (ZIP Play Store)"
bash "$MOBILE/scripts/export-for-aistudio.sh"

echo ""
echo "==> 4/6 Smoke tests"
python3 "$MOBILE/scripts/smoke-mobile-apps.py" || true

echo ""
echo "==> 5/6 Build AAB (se JDK disponível)"
if bash "$MOBILE/scripts/build-release-aab.sh"; then
  echo "AAB gerado."
else
  echo "[INFO] AAB não gerado — use Google AI Studio ou instale Android Studio + JDK 17."
fi

echo ""
echo "==> 6/6 Abrir Google AI Studio"
open "https://aistudio.google.com/apps?source=start" 2>/dev/null || true

cat <<EOF

══════════════════════════════════════════════════════════
 NaIntegra Lex — pronto para Google Play (AI Studio)
══════════════════════════════════════════════════════════

  ZIP export:     mobile/dist/naintegra-lex-aistudio.zip
  Prompt:         mobile/aistudio/PROMPT.md
  Asset links:    https://www.naintegracursos.com.br/.well-known/assetlinks.json
  Package:        br.com.naintegracursos.lex

  AI Studio:
    1. Build an Android app
    2. Cole PROMPT.md + ícone icon-512.png
    3. Teste no emulador
    4. Connect Play Console → Internal Test Track

  Após upload Play (Play App Signing):
    python3 mobile/scripts/update-assetlinks.py --add "SHA256_PLAY"
    python3 scripts/sync_site_root_to_cursos.py --push

EOF
