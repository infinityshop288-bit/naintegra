#!/usr/bin/env python3
"""Importa flashcards de CSV (categoria, pergunta, resposta) para Lex e NaIntegra Cursos."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

import httpx

DEFAULT_URL = "https://voybsggeedpwcfdadnzt.supabase.co"
DEFAULT_ANON = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6"
    "InZveWJzZ2dlZWRwd2NmZGFkbnp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNzU2MTQs"
    "ImV4cCI6MjA4ODc1MTYxNH0.dy5AgSd1VWdP4WLGXy5V89pA4jgHijngHJjScApOo70"
)
CURSOS_FLASHCARD_USER = "927146c5-42b6-4ce8-93f1-2ee52ca38e45"


def cfg() -> tuple[str, str, str | None]:
    url = os.environ.get("LEX_AGENT_SUPABASE_URL", DEFAULT_URL).rstrip("/")
    service = os.environ.get("LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", "").strip() or None
    anon = os.environ.get("LEX_FLASHCARDS_EXPORT_ANON_KEY", DEFAULT_ANON)
    return url, anon, service


def read_csv(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pergunta = (row.get("pergunta") or row.get("front") or "").strip()
            resposta = (row.get("resposta") or row.get("back") or "").strip()
            if not pergunta or not resposta:
                continue
            rows.append(
                {
                    "categoria": (row.get("categoria") or row.get("category") or "").strip(),
                    "pergunta": pergunta,
                    "resposta": resposta,
                }
            )
    return rows


def ensure_lex_deck(
    client: httpx.Client, base: str, headers: dict, *, slug: str, name: str, category: str, sort_order: int
) -> str:
    res = client.get(
        f"{base}/rest/v1/flashcard_decks?select=id,slug,name&slug=eq.{slug}",
        headers=headers,
    )
    res.raise_for_status()
    found = res.json()
    if found:
        return found[0]["id"]

    ins = client.post(
        f"{base}/rest/v1/flashcard_decks",
        headers={**headers, "Prefer": "return=representation"},
        json={"slug": slug, "name": name, "category": category, "sort_order": sort_order},
    )
    if ins.status_code in (401, 403):
        res = client.get(
            f"{base}/rest/v1/flashcard_decks?select=id&slug=eq.{slug}",
            headers=headers,
        )
        res.raise_for_status()
        rows = res.json()
        if rows:
            return rows[0]["id"]
        raise RuntimeError(
            "Deck não encontrado e sem permissão para criar. "
            "Aplique sql/add_licitacoes_flashcards_deck.sql ou use service role."
        )
    ins.raise_for_status()
    return ins.json()[0]["id"]


def ingest_lex_cards(
    client: httpx.Client, base: str, headers: dict, *, discipline: str, cards: list[dict[str, str]]
) -> int:
    rows = [
        {"discipline": discipline, "front": c["pergunta"], "back": c["resposta"], "highlight": None}
        for c in cards
    ]
    res = client.post(
        f"{base}/rest/v1/rpc/ingest_flashcards_batch",
        headers=headers,
        json={"rows": rows},
    )
    res.raise_for_status()
    return int(res.json())


def ingest_cursos_cards(
    client: httpx.Client,
    base: str,
    headers: dict,
    *,
    discipline: str,
    cards: list[dict[str, str]],
    user_id: str,
) -> int:
    payload = [
        {
            "user_id": user_id,
            "discipline": discipline,
            "front": c["pergunta"],
            "back": c["resposta"],
            "difficulty": "medium",
            "review_count": 0,
        }
        for c in cards
    ]
    chunk = 100
    inserted = 0
    for i in range(0, len(payload), chunk):
        batch = payload[i : i + chunk]
        res = client.post(f"{base}/rest/v1/flashcards", headers=headers, json=batch)
        res.raise_for_status()
        inserted += len(batch)
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa flashcards CSV para Lex / NaIntegra Cursos")
    parser.add_argument("csv_path", type=Path, help="CSV com colunas categoria, pergunta, resposta")
    parser.add_argument("--deck-name", default="Licitações — Lei 14.133/2021")
    parser.add_argument("--deck-slug", default="licitacoes-lei-14133")
    parser.add_argument("--deck-category", default="Direito Administrativo")
    parser.add_argument("--deck-sort-order", type=int, default=15)
    parser.add_argument("--skip-cursos", action="store_true", help="Não inserir em public.flashcards")
    parser.add_argument("--export-fallback", action="store_true", help="Roda export_lex_flashcards_catalog.py")
    args = parser.parse_args()

    cards = read_csv(args.csv_path)
    if not cards:
        print("Nenhum card no CSV.", file=sys.stderr)
        return 1

    base, anon, service = cfg()
    key = service or anon
    lex_headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept-Profile": "lex",
        "Content-Profile": "lex",
        "Content-Type": "application/json",
    }
    pub_headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept-Profile": "public",
        "Content-Profile": "public",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    with httpx.Client(timeout=120.0) as client:
        deck_id = ensure_lex_deck(
            client,
            base,
            lex_headers,
            slug=args.deck_slug,
            name=args.deck_name,
            category=args.deck_category,
            sort_order=args.deck_sort_order,
        )
        lex_n = ingest_lex_cards(client, base, lex_headers, discipline=args.deck_name, cards=cards)
        cursos_n = 0
        if not args.skip_cursos and service:
            cursos_n = ingest_cursos_cards(
                client,
                base,
                pub_headers,
                discipline=args.deck_name,
                cards=cards,
                user_id=CURSOS_FLASHCARD_USER,
            )

    print(f"Deck lex: {args.deck_slug} ({deck_id})")
    print(f"Inseridos no Lex: {lex_n} cards")
    if not args.skip_cursos:
        if service:
            print(f"Inseridos no NaIntegra Cursos (public.flashcards): {cursos_n} cards")
        else:
            print("NaIntegra Cursos: omitido (defina LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY)")

    if args.export_fallback:
        repo = Path(__file__).resolve().parent.parent
        export = repo / "scripts" / "export_lex_flashcards_catalog.py"
        if export.is_file():
            os.system(f"{sys.executable} {export}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
