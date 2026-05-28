#!/usr/bin/env sh
# Copia legislação AGU do scraper para data/legislacao_agu/ e ingere no Lex (Supabase).
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SCRAPER="${NAINTEGRACURSOS_SCRAPER_PATH:-/Users/luizcarlos/naintegracursos-scraper}"
SRC="$SCRAPER/data/processed/legislacao_agu"
DEST="$ROOT/data/legislacao_agu"
STATE_SRC="$SCRAPER/data/agu/legislacao_state.json"

if [ ! -d "$SRC" ]; then
  echo "Erro: pasta do scraper ausente: $SRC" >&2
  exit 1
fi

mkdir -p "$DEST"
rsync -a --delete "$SRC/" "$DEST/"
if [ -f "$STATE_SRC" ]; then
  mkdir -p "$ROOT/data/agu"
  cp "$STATE_SRC" "$ROOT/data/agu/legislacao_state.json"
fi
echo "==> Sincronizado: $DEST ($(find "$DEST" -name '*.jsonl' | wc -l | tr -d ' ') arquivo(s))"

if [ -f .env ]; then set -a; . ./.env; set +a; fi
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export AGU_LEGIS_INPUT_DIR="$DEST"
python3 "$ROOT/scripts/ingest_agu_legislacao_from_scraper.py" "$@"

echo "==> Verificando correspondência título × URL × texto"
python3 "$ROOT/scripts/verify_legislacao_correspondence.py" --json-out "$ROOT/data/reports/legislacao_correspondence.json"
