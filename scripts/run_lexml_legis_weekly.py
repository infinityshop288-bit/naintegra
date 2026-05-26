#!/usr/bin/env python3
"""Wrapper CLI — descoberta LEXML semanal e promoção no NaIntegra Lex."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from naintegra_lex_agent.lexml_legis_weekly import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
