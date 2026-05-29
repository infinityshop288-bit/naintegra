#!/usr/bin/env python3
"""Extrai CP IURIS 2025 (PDF + Ollama) em loop até concluir."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from naintegra_lex_agent.cp_iuris_loop import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
