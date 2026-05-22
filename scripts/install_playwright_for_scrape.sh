#!/usr/bin/env bash
# Instala dependência opcional e o Chromium usado pelo harvest headless.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 -m pip install -e "${ROOT}[playwright]"
python3 -m playwright install chromium
