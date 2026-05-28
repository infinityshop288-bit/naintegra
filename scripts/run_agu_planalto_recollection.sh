#!/usr/bin/env sh
# Re-coleta Planalto (encoding correto) → data/legislacao_agu_recollection/ (backup separado).
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SOURCE="${AGU_LEGIS_SOURCE_DIR:-$ROOT/data/legislacao_agu}"
BACKUP="${AGU_LEGIS_BACKUP_ROOT:-$ROOT/data/legislacao_agu_recollection}"

if [ -f .env ]; then set -a; . ./.env; set +a; fi
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export AGU_LEGIS_SOURCE_DIR="$SOURCE"
export AGU_LEGIS_BACKUP_ROOT="$BACKUP"

echo "==> Re-coleta Planalto → $BACKUP"
python3 "$ROOT/scripts/recollect_agu_planalto_legislacao.py" --verify "$@"
