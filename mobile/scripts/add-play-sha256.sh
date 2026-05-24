#!/usr/bin/env bash
# Após 1º upload Play Console: adiciona SHA-256 App Signing e publica assetlinks.
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$MOBILE/.." && pwd)"

if [[ $# -lt 1 ]]; then
  cat <<EOF
Uso: $0 SHA256_DO_PLAY_CONSOLE

Onde copiar:
  Play Console → NaIntegra Lex → Configuração → Integridade do app
  → Certificado de assinatura do app → SHA-256

Exemplo:
  $0 AA:BB:CC:DD:...
EOF
  exit 1
fi

python3 "$MOBILE/scripts/update-assetlinks.py" --add "$1"
python3 "$ROOT/scripts/sync_site_root_to_cursos.py" --push || true

echo ""
echo "Validar:"
curl -sS "https://www.naintegracursos.com.br/.well-known/assetlinks.json?v=$(date +%s)" | python3 -m json.tool
