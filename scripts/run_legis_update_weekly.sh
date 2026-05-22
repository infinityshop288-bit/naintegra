#!/usr/bin/env bash
# Atualização semanal da legislação Planalto → Supabase + legis_summaries.json
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
exec python3 scripts/update_lex_legislacao_semanal.py "$@"
