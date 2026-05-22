#!/usr/bin/env bash
# Consolida legislação/jurisprudência coletada → Supabase norma_chunks (Lex).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -c "from naintegra_lex_agent.norma_consolidate_loop import main_sync; main_sync()"
