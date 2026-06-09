#!/usr/bin/env python3
"""Gera posts do calendário → fila Supabase (aguardando_aprovacao). Não publica no Instagram."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from naintegra_meta.pipeline import run_content_pipeline  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline de conteúdo @delegadoluizcarlos")
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Quantos dias a partir de --start (default: 1 = hoje)",
    )
    parser.add_argument("--start", type=str, default=None, help="Data ISO (ex. 2026-06-03)")
    parser.add_argument("--month", type=str, default=None, help="Calendário YYYY-MM")
    parser.add_argument("--provider", type=str, default=None, help="ollama|anthropic|gemini|grok|...")
    parser.add_argument("--dry-run", action="store_true", help="Só imprime JSON, não grava")
    parser.add_argument(
        "--fill-month",
        action="store_true",
        help="Preenche todos os dias restantes do mês no calendário",
    )
    args = parser.parse_args()

    start: date | None = None
    if args.start:
        start = date.fromisoformat(args.start)

    days = args.days
    if args.fill_month:
        from naintegra_meta.content_calendar import load_calendar

        ref = start or date.today()
        cal = load_calendar(args.month or ref.strftime("%Y-%m"))
        all_dates = [d["date"] for d in cal.get("days") or []]
        if start:
            days = sum(1 for d in all_dates if d >= start.isoformat())
        else:
            days = len(all_dates)

    result = run_content_pipeline(
        days=days,
        start_date=start,
        month=args.month,
        provider=args.provider,  # type: ignore[arg-type]
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
