#!/usr/bin/env bash
# Loop contínuo: scrape (Playwright/QConcurso quando LEX_AGENT_SCRAPE_LOOP_MODE=playwright_harvest)
# → fusão → normalize/manifest. Use com systemd, supervisord ou screen/tmux.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
exec naintegra-questions-loop
