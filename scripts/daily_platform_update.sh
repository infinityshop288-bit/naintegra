#!/usr/bin/env bash
# Atualização completa da plataforma /xxx/ (local ou CI).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PY:-python3}"

if [[ -f data/prio3_analysis/.venv/bin/python ]]; then
  PY="data/prio3_analysis/.venv/bin/python"
fi

echo "=== Atualização diária dashboard PRIO3 ==="
bash data/prio3_analysis/refresh_market.sh
"$PY" scripts/export_prio3_snapshots.py
if [[ -f .env.deploy ]]; then set -a; source .env.deploy; set +a; fi
"$PY" scripts/build_prio3_deploy.py --skip-snapshots
echo "[OK] Bundle em xxx/ — rode sync_prio3_to_cursos.py --skip-build --push para publicar"
