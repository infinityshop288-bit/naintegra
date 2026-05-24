#!/usr/bin/env bash
# Assistente local — prepara clipboard e abre AI Studio (13 telas).
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$MOBILE/.." && pwd)"
AISTUDIO="$MOBILE/aistudio"
ICON="$ROOT/web/lex/icons/icon-512.png"
URL="https://aistudio.google.com/apps?source=start"

step() { echo ""; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; echo "  $1"; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }

step "1/5 — Export ZIP atualizado"
bash "$MOBILE/scripts/export-for-aistudio.sh" | tail -3

step "2/5 — Prompt copiado para área de transferência"
if command -v pbcopy >/dev/null 2>&1; then
  pbcopy < "$AISTUDIO/PROMPT-COPIAR.txt"
  echo "✓ PROMPT-COPIAR.txt → clipboard (Cmd+V no AI Studio)"
else
  echo "Abra manualmente: $AISTUDIO/PROMPT-COPIAR.txt"
fi

step "3/5 — Abrindo Google AI Studio + arquivos"
open "$URL" 2>/dev/null || true
open "$AISTUDIO/GUIA-TELA-A-TELA.md" 2>/dev/null || true
open "$ICON" 2>/dev/null || true
open "$MOBILE/dist/naintegra-lex-aistudio.zip" 2>/dev/null || true

step "4/5 — O que fazer AGORA no AI Studio"
cat <<'INSTR'

  1. Faça login Google (conta Play Console)
  2. Clique: Apps → Build an Android app
  3. Cole o prompt: Cmd+V (já está no clipboard)
  4. Anexe icon-512.png (Preview aberto)
  5. Clique Generate / Build

INSTR

step "5/5 — Após gerar, teste no emulador"
cat <<'TEST'

  ☐ https://www.naintegracursos.com.br/lex/ carrega
  ☐ Lei Seca abre
  ☐ Login Google funciona
  ☐ Publish → Connect Play Console → Internal Test Track

  Problemas? Use REFINAMENTOS-COPIAR.txt no chat do AI Studio.

TEST

echo ""
echo "Package: br.com.naintegracursos.lex"
echo "Guia:    mobile/aistudio/GUIA-TELA-A-TELA.md"
echo ""
read -r -p "Pressione ENTER quando tiver colado o prompt e anexado o ícone… " _

step "Refinamentos — copiar para clipboard?"
read -r -p "Teve erro no preview? (s/n): " err
if [[ "$err" == "s" || "$err" == "S" ]]; then
  echo "Abra REFINAMENTOS-COPIAR.txt e cole o bloco do problema."
  open "$AISTUDIO/REFINAMENTOS-COPIAR.txt"
fi

read -r -p "Pronto para Play Store metadata? (s/n): " meta
if [[ "$meta" == "s" || "$meta" == "S" ]] && command -v pbcopy >/dev/null 2>&1; then
  pbcopy < "$AISTUDIO/PLAY-STORE-COPIAR.txt"
  echo "✓ PLAY-STORE-COPIAR.txt → clipboard"
  open "https://play.google.com/console" 2>/dev/null || true
fi

echo ""
echo "Após upload Internal Test, rode:"
echo "  python3 mobile/scripts/update-assetlinks.py --add \"SHA256_DO_PLAY\""
echo "  python3 scripts/sync_site_root_to_cursos.py --push"
