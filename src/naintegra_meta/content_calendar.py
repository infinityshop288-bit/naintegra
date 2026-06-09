"""Calendário editorial mensal — slots por dia."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[2]
CALENDAR_DIR = REPO / "data" / "delegado" / "calendars"
TZ_BR = ZoneInfo("America/Sao_Paulo")


def load_calendar(month: str | None = None) -> dict[str, Any]:
    """month: YYYY-MM ou None → mês atual (BR)."""

    if month:
        stem = month.replace("/", "-")[:7]
    else:
        stem = datetime.now(TZ_BR).strftime("%Y-%m")
    path = CALENDAR_DIR / f"content_calendar_{stem.replace('-', '_')}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Calendário não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def slot_for_date(d: date, calendar: dict[str, Any] | None = None) -> dict[str, Any] | None:
    cal = calendar or load_calendar(d.strftime("%Y-%m"))
    key = d.isoformat()
    for day in cal.get("days") or []:
        if day.get("date") == key:
            return day
    return None


def slots_from_today(
    *,
    days: int = 1,
    month: str | None = None,
    start: date | None = None,
) -> list[dict[str, Any]]:
    cal = load_calendar(month)
    start_d = start or datetime.now(TZ_BR).date()
    out: list[dict[str, Any]] = []
    for i in range(days):
        d = start_d + timedelta(days=i)
        slot = slot_for_date(d, cal)
        if slot:
            out.append(slot)
    return out


def calendar_summary(month: str | None = None) -> dict[str, Any]:
    cal = load_calendar(month)
    return {
        "month": cal.get("month"),
        "title": cal.get("title"),
        "style_reference": cal.get("style_reference"),
        "total_days": len(cal.get("days") or []),
        "days": cal.get("days") or [],
    }
