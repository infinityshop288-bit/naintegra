#!/usr/bin/env bash
# Um ciclo: harvest Playwright (se LEX_AGENT_SCRAPE_LOOP_MODE=playwright_harvest) + fusão + normalize.
# Útil para validar objetivas/discursivas (LEX_AGENT_SCRAPE_HARVEST_EMIT_MODE=all_with_gabarito) sem loop infinito.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# Preserva overrides da linha de comandos antes de source .env (senão o .env sobrescreve).
_CALLER_HEADED_SET=
if [[ "${LEX_AGENT_SCRAPE_HARVEST_HEADED+set}" == set ]]; then
  _CALLER_HEADED_VALUE="$LEX_AGENT_SCRAPE_HARVEST_HEADED"
  _CALLER_HEADED_SET=1
fi
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
export LEX_AGENT_QUESTIONS_LOOP_RUN_ONCE=true
if [[ -n "$_CALLER_HEADED_SET" ]]; then
  export LEX_AGENT_SCRAPE_HARVEST_HEADED="$_CALLER_HEADED_VALUE"
fi
unset _CALLER_HEADED_SET _CALLER_HEADED_VALUE
exec naintegra-questions-loop
