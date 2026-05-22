#!/usr/bin/env bash
# Publica NaIntegra Lex no docroot do site (ajuste REMOTE_PATH).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_PATH="${LEX_SITE_PATH:-/home/*/domains/naintegracursos.com.br/public_html/lex}"

bash "$ROOT/scripts/publish_lex_static.sh"

if [[ -d "$REMOTE_PATH" ]]; then
  rsync -av --delete "$ROOT/lex/" "$REMOTE_PATH/"
  echo "Lex publicado em $REMOTE_PATH"
else
  echo "Pasta remota não encontrada: $REMOTE_PATH"
  echo "Defina LEX_SITE_PATH ou copie manualmente:"
  echo "  rsync -av $ROOT/lex/ SEU_SERVIDOR:public_html/lex/"
fi
