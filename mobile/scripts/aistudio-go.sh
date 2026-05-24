#!/usr/bin/env bash
# Prepara tudo e abre AI Studio (sem prompts interativos).
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$MOBILE/.." && pwd)"
AISTUDIO="$MOBILE/aistudio"
ICON="$ROOT/web/lex/icons/icon-512.png"

echo "==> Export"
bash "$MOBILE/scripts/export-for-aistudio.sh" | tail -2

echo "==> Clipboard: prompt principal"
if command -v pbcopy >/dev/null 2>&1; then
  pbcopy < "$AISTUDIO/PROMPT-COPIAR.txt"
  echo "OK — Cmd+V no AI Studio"
fi

echo "==> Abrindo"
open "https://aistudio.google.com/apps?source=start"
open "$AISTUDIO/GUIA-TELA-A-TELA.md"
open "$ICON"
open "$MOBILE/dist/naintegra-lex-aistudio.zip"

echo ""
echo "FAÇA AGORA (3 passos):"
echo "  1. Login Google → Apps → Build an Android app"
echo "  2. Cmd+V (prompt) + anexar icon-512.png → Generate"
echo "  3. Preview → Publish → Internal Test Track"
