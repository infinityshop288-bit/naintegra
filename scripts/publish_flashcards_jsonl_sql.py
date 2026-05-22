#!/usr/bin/env python3
"""Publica cards.jsonl no schema lex via SQL (para uso com Supabase MCP ou psql)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from naintegra_lex_agent.flashcards_from_docx import (  # noqa: E402
    DECK_CATALOG,
    FlashcardDraft,
    guess_discipline,
)


def _sql_str(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def load_cards(path: Path) -> list[FlashcardDraft]:
    cards: list[FlashcardDraft] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            cards.append(
                FlashcardDraft(
                    page_index=int(row["page_index"]),
                    card_index=int(row["card_index"]),
                    front=str(row["front"]),
                    back=str(row["back"]),
                    discipline=row.get("discipline"),
                    highlight=row.get("highlight"),
                    source_ref=row.get("source_ref"),
                )
            )
    return cards


def build_insert_sql(cards: list[FlashcardDraft], deck_ids: dict[str, str], sort_start: dict[str, int]) -> str:
    counters = dict(sort_start)
    values: list[str] = []
    for card in cards:
        discipline = card.discipline or guess_discipline(f"{card.front}\n{card.back}")
        deck_id = deck_ids.get(discipline) or deck_ids["Direito Administrativo"]
        counters[deck_id] = counters.get(deck_id, 0) + 1
        values.append(
            "("
            f"{_sql_str(deck_id)}::uuid, "
            f"{_sql_str(card.front)}, "
            f"{_sql_str(card.back)}, "
            f"{_sql_str(card.highlight)}, "
            f"{counters[deck_id]}"
            ")"
        )
    if not values:
        return ""
    return (
        "INSERT INTO lex.flashcards (deck_id, front, back, highlight, sort_order) VALUES\n"
        + ",\n".join(values)
        + ";\n"
    )


def fetch_deck_ids_sql() -> str:
    names = [name for _, name, _ in DECK_CATALOG]
    in_list = ", ".join(_sql_str(n) for n in names)
    return f"SELECT name, id::text FROM lex.flashcard_decks WHERE name IN ({in_list});"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path, help="Arquivo cards.jsonl gerado pelo pipeline.")
    parser.add_argument("--batch-size", type=int, default=80)
    parser.add_argument("--offset", type=int, default=0, help="Pular N cards (retomada).")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--deck-ids-json",
        type=Path,
        help="JSON {\"Direito Constitucional\": \"uuid\", ...} — se omitido, imprime query para obter IDs.",
    )
    parser.add_argument(
        "--sort-start-json",
        type=Path,
        help="JSON {deck_id: max_sort_order} para continuar numeração.",
    )
    args = parser.parse_args()

    cards = load_cards(args.jsonl.resolve())
    if args.offset:
        cards = cards[args.offset :]
    if args.limit is not None:
        cards = cards[: args.limit]

    if args.deck_ids_json is None:
        print("-- Execute no Supabase para obter deck IDs:")
        print(fetch_deck_ids_sql())
        print(f"-- Total cards a publicar: {len(cards)}")
        return 0

    deck_ids = json.loads(args.deck_ids_json.read_text(encoding="utf-8"))
    sort_start: dict[str, int] = {}
    if args.sort_start_json and args.sort_start_json.is_file():
        sort_start = json.loads(args.sort_start_json.read_text(encoding="utf-8"))

    for i in range(0, len(cards), args.batch_size):
        batch = cards[i : i + args.batch_size]
        sql = build_insert_sql(batch, deck_ids, sort_start)
        if not sql:
            continue
        print(f"-- batch offset {args.offset + i} size {len(batch)}")
        print(sql)

    return 0


if __name__ == "__main__":
    sys.exit(main())
