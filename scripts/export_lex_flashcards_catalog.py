#!/usr/bin/env python3
"""Exporta lex.flashcard_decks + lex.flashcards → web/lex/data/flashcards.json."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "web" / "lex" / "data" / "flashcards.json"


def _cfg() -> tuple[str, str]:
    url = os.environ.get("LEX_AGENT_SUPABASE_URL", "https://voybsggeedpwcfdadnzt.supabase.co").strip()
    key = os.environ.get("LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key:
        key = os.environ.get(
            "LEX_FLASHCARDS_EXPORT_ANON_KEY",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZveWJzZ2dlZWRwd2NmZGFkbnp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNzU2MTQsImV4cCI6MjA4ODc1MTYxNH0.dy5AgSd1VWdP4WLGXy5V89pA4jgHijngHJjScApOo70",
        )
    return url.rstrip("/"), key


def fetch_paged(client: httpx.Client, base: str, headers: dict, table: str, query: str) -> list:
    out: list = []
    offset = 0
    limit = 1000
    while True:
        url = f"{base}/rest/v1/{table}?{query}&limit={limit}&offset={offset}"
        res = client.get(url, headers=headers)
        res.raise_for_status()
        batch = res.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return out


def main() -> int:
    base, key = _cfg()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept-Profile": "lex",
    }
    with httpx.Client(timeout=120.0) as client:
        decks = fetch_paged(
            client, base, headers, "flashcard_decks", "select=*&order=sort_order.asc"
        )
        cards = fetch_paged(
            client,
            base,
            headers,
            "flashcards",
            "select=*&order=deck_id.asc,sort_order.asc",
        )

    by_deck: dict[str, list] = {}
    for c in cards:
        by_deck.setdefault(c["deck_id"], []).append(c)

    payload_decks = []
    total_cards = 0
    for d in decks:
        deck_cards = sorted(by_deck.get(d["id"], []), key=lambda x: x.get("sort_order") or 0)
        total_cards += len(deck_cards)
        payload_decks.append(
            {
                "slug": d["slug"],
                "name": d["name"],
                "category": d["category"],
                "cards": [
                    {
                        "front": c["front"],
                        "back": c["back"],
                        "highlight": c.get("highlight"),
                    }
                    for c in deck_cards
                ],
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deck_count": len(payload_decks),
        "card_count": total_cards,
        "decks": payload_decks,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # Valida escrita (evita deploy de JSON truncado).
    json.loads(OUT.read_text(encoding="utf-8"))
    print(f"Exportados {total_cards} cards em {len(payload_decks)} decks → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
