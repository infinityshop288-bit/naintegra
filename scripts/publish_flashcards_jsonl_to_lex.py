#!/usr/bin/env python3
"""Publica cards.jsonl no NaIntegra Lex (schema lex) via SQL em lotes."""

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
    build_insert_sql,
    guess_discipline,
    load_processed_page_keys,
)


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


def default_deck_ids() -> dict[str, str]:
    """IDs atuais do projeto NaIntegra Lex (voybsggeedpwcfdadnzt)."""
    return {name: deck_id for _, name, deck_id in [
        ("dir-const", "Direito Constitucional", "4fcc5e8c-4353-435f-8163-0e00764a75a1"),
        ("dir-proc-civil", "Direito Processual Civil", "af6f3a62-0068-4ca3-b852-f8f37b691c08"),
        ("dir-adm", "Direito Administrativo", "93b2a3df-c79d-43bd-8019-d669eab5dd61"),
        ("dir-penal-geral", "Direito Penal - Parte Geral", "41f9a7ca-3b0f-4f60-afd2-da31bc1b859a"),
        ("dir-civil-obrig", "Direito Civil - Obrigações e Contratos", "6776ba18-7814-48ac-975b-324eab16e951"),
        ("dir-eleitoral", "Direito Eleitoral", "a09f2cbc-f5db-4f9d-9394-2dd7ba9c68be"),
        ("jurisprudencia", "Jurisprudência", "077745a2-cb35-4c81-b8dc-af6aa72ace78"),
        ("dir-civil-geral", "Direito Civil - Parte Geral", "9b13a457-dfed-44e2-97cf-e545a7ab4048"),
        ("dir-penal-especial", "Direito Penal - Parte Especial", "f3a6fd21-d08f-4729-8b1a-577be313df91"),
        ("dir-financeiro", "Direito Financeiro", "37da87ca-36ec-4c13-80a4-9bbc4528d5aa"),
        ("tutela-coletiva", "Tutela Coletiva e Direito Processual Coletivo", "4e5d0149-824a-4ae4-8dc7-4f05550e4486"),
        ("lei-improbidade", "Lei de Improbidade Administrativa", "8f216f4e-e9c2-4658-bca8-33740905dcfb"),
        ("dir-economico", "Direito Econômico", "1fcaf1ef-49ba-4665-9559-b5049f0ec0d0"),
        ("dir-previdenciario", "Direito Previdenciário", "a0191700-fa80-4000-a58b-a22adcbbb3b6"),
    ]}


def default_sort_start() -> dict[str, int]:
    return {
        "4fcc5e8c-4353-435f-8163-0e00764a75a1": 1249,
        "af6f3a62-0068-4ca3-b852-f8f37b691c08": 1068,
        "93b2a3df-c79d-43bd-8019-d669eab5dd61": 787,
        "41f9a7ca-3b0f-4f60-afd2-da31bc1b859a": 634,
        "6776ba18-7814-48ac-975b-324eab16e951": 633,
        "a09f2cbc-f5db-4f9d-9394-2dd7ba9c68be": 505,
        "077745a2-cb35-4c81-b8dc-af6aa72ace78": 500,
        "9b13a457-dfed-44e2-97cf-e545a7ab4048": 399,
        "f3a6fd21-d08f-4729-8b1a-577be313df91": 356,
        "37da87ca-36ec-4c13-80a4-9bbc4528d5aa": 248,
        "4e5d0149-824a-4ae4-8dc7-4f05550e4486": 232,
        "8f216f4e-e9c2-4658-bca8-33740905dcfb": 221,
        "1fcaf1ef-49ba-4665-9559-b5049f0ec0d0": 150,
        "a0191700-fa80-4000-a58b-a22adcbbb3b6": 73,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--batch-size", type=int, default=60)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out-dir", type=Path, default=REPO / "data" / "flashcards_verbetes" / "sql_batches")
    parser.add_argument("--state", type=Path, default=REPO / "data" / "flashcards_verbetes" / "publish_state.json")
    args = parser.parse_args()

    cards = load_cards(args.jsonl.resolve())
    if args.offset:
        cards = cards[args.offset :]
    if args.limit is not None:
        cards = cards[: args.limit]

    deck_ids = default_deck_ids()
    sort_start = default_sort_start()
    if args.state.is_file():
        try:
            st = json.loads(args.state.read_text(encoding="utf-8"))
            sort_start.update(st.get("sort_counters") or {})
            args.offset = int(st.get("next_offset") or args.offset)
            cards = load_cards(args.jsonl.resolve())[args.offset :]
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    args.out_dir.mkdir(parents=True, exist_ok=True)
    counters = dict(sort_start)
    written = 0
    for i in range(0, len(cards), args.batch_size):
        batch = cards[i : i + args.batch_size]
        sql = build_insert_sql(batch, deck_ids, counters)
        if not sql:
            continue
        out = args.out_dir / f"batch_{args.offset + i:06d}.sql"
        out.write_text(sql, encoding="utf-8")
        written += 1

    args.state.write_text(
        json.dumps(
            {"next_offset": args.offset + len(cards), "sort_counters": counters, "batches": written},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Gerados {written} arquivos SQL em {args.out_dir} ({len(cards)} cards).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
