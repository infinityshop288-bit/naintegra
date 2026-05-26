#!/usr/bin/env bash
# LEXML semanal → crawl_inbox → promoção Planalto no Supabase + export offline Lex
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
exec python3 scripts/run_lexml_legis_weekly.py "$@"
