#!/usr/bin/env bash
# Copia web/lex → lex/ (pasta servida em naintegracursos.com.br/lex)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/web/lex"
DST="$ROOT/lex"
rm -rf "$DST"
mkdir -p "$DST"
rsync -a --delete \
  --exclude '.DS_Store' \
  "$SRC/" "$DST/"
echo "Publicado em $DST ($(du -sh "$DST" | awk '{print $1}'))"
echo "Envie o conteúdo de lex/ para public_html/lex/ no servidor."
