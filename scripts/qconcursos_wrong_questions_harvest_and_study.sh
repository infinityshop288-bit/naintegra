#!/usr/bin/env bash
# Fluxo: 1 ciclo questions-loop (harvest na URL das erradas do .env)
# → ingest → estudo IA → HTML de revisão.
# Configure no .env:
#   LEX_AGENT_SCRAPE_LOOP_MODE=playwright_harvest
#   LEX_AGENT_SCRAPE_HARVEST_START_URL=https://www.qconcursos.com/questoes-de-concursos/questoes?my_questions=wrong&per_page=20
#   LEX_AGENT_SCRAPE_HARVEST_EMIT_MODE=wrong_only   # ou all_with_gabarito se consolidate ficar vazio
#   LEX_AGENT_SCRAPE_HARVEST_EMIT_UNKNOWN_WRONG=true # ajuda quando a API não marca erro explicitamente
#   QC_STUDY_STUDY_PROMPT_PROFILE=cited_solution    # solução com lei + jurisprudência (conhecimento do modelo)
#   QC_STUDY_ANTHROPIC_API_KEY=… ou OPENAI
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

echo "== 1/2 Harvest + organize (run_once) =="
export LEX_AGENT_QUESTIONS_LOOP_RUN_ONCE=true
naintegra-questions-loop

echo "== 2/2 Ingest → estudo IA → HTML =="
exec naintegra-qconcursos-studies run "$@"
