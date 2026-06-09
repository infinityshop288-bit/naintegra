"""CLI: naintegra-delegado-pipeline"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date

from naintegra_meta.pipeline import run_content_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline de conteúdo @delegadoluizcarlos")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--month", type=str, default=None)
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fill-month", action="store_true")
    args = parser.parse_args()

    start = date.fromisoformat(args.start) if args.start else None
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
    raise SystemExit(0 if result.get("ok") else 1)
