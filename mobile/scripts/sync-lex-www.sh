#!/usr/bin/env bash
# Copia web/lex → mobile/www (assets empacotados no app).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/web/lex"
DST="$ROOT/mobile/www"
if [[ ! -d "$SRC" ]]; then
  echo "Origem não encontrada: $SRC" >&2
  exit 1
fi
mkdir -p "$DST"
rsync -a --delete \
  --exclude '.DS_Store' \
  --exclude 'node_modules' \
  "$SRC/" "$DST/"
echo "Sincronizado: $SRC → $DST ($(find "$DST" -type f | wc -l | tr -d ' ') arquivos)"
