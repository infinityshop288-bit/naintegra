#!/usr/bin/env bash
# Abre assistentes Play + AI Studio, valida assetlinks, copia prompt.
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$MOBILE/.." && pwd)"

echo "==> Validar Digital Asset Links (Google API)"
curl -sS "https://digitalassetlinks.googleapis.com/v1/statements:list?source.web.site=https://www.naintegracursos.com.br&relation=delegate_permission/common.handle_all_urls" \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)
s=d.get('statements',[])
if not s:
    print('AVISO: nenhuma statement'); sys.exit(1)
t=s[0].get('target',{}).get('androidApp',{})
print('OK package:', t.get('packageName'))
print('OK sha256:', t.get('certificate',{}).get('sha256Fingerprint'))
"

echo ""
echo "==> Gerar assets Play Store (se necessario)"
if [[ ! -f "$MOBILE/store-assets/generated/feature-graphic-1024x500.png" ]]; then
  python3 "$MOBILE/scripts/generate-store-assets.py"
fi

echo ""
echo "==> Export ZIP"
bash "$MOBILE/scripts/export-for-aistudio.sh" | tail -2

echo ""
echo "==> Clipboard: prompt AI Studio"
pbcopy < "$MOBILE/aistudio/PROMPT-COPIAR.txt" 2>/dev/null && echo "Prompt copiado (Cmd+V)"

echo ""
echo "==> Abrindo"
open "$MOBILE/store-assets/play-console-helper.html"
open "$MOBILE/store-assets/generated"
open "https://aistudio.google.com/apps?source=start"
open "https://play.google.com/console/u/0/developers/-/app/create"

cat <<'EOF'

═══════════════════════════════════════════════════════
 PASSO A PASSO (facaa agora)
═══════════════════════════════════════════════════════

 AI STUDIO:
   1. Build an Android app
   2. Cmd+V (prompt) + icon-512.png
   3. Generate → Preview → Internal Test Track

 PLAY CONSOLE (helper HTML aberto):
   1. Criar app → copiar campos do helper
   2. Upload capturas de generated/
   3. Internal testing → aguardar .aab do AI Studio

 DEPOIS DO UPLOAD:
   bash mobile/scripts/add-play-sha256.sh "SHA256_PLAY_CONSOLE"

EOF
