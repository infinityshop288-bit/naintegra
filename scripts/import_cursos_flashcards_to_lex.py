#!/usr/bin/env python3
"""Importa public.flashcards (NaIntegra Cursos) → lex.flashcard_decks + lex.flashcards."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
SQL = REPO / "sql" / "import_cursos_flashcards_to_lex.sql"

DECKS = [
    ("dir-const", "Direito Constitucional", "Direito Público", 1),
    ("dir-proc-civil", "Direito Processual Civil", "Processo", 2),
    ("dir-proc-penal", "Direito Processual Penal", "Processo", 3),
    ("dir-adm", "Direito Administrativo", "Direito Público", 4),
    ("dir-penal-geral", "Direito Penal - Parte Geral", "Direito Público", 5),
    ("dir-civil-obrig", "Direito Civil - Obrigações e Contratos", "Direito Privado", 6),
    ("dir-eleitoral", "Direito Eleitoral", "Direito Público", 7),
    ("jurisprudencia", "Jurisprudência", "Jurisprudência", 8),
    ("dir-civil-geral", "Direito Civil - Parte Geral", "Direito Privado", 9),
    ("dir-penal-especial", "Direito Penal - Parte Especial", "Direito Público", 10),
    ("dir-financeiro", "Direito Financeiro", "Direito Público", 11),
    ("tutela-coletiva", "Tutela Coletiva e Direito Processual Coletivo", "Processo", 12),
    ("lei-improbidade", "Lei de Improbidade Administrativa", "Direito Público", 13),
    ("dir-economico", "Direito Econômico", "Direito Público", 14),
    ("dir-previdenciario", "Direito Previdenciário", "Direito Privado", 15),
    ("licitacoes-lei-14133", "Licitações — Lei 14.133/2021", "Direito Administrativo", 16),
]


def _cfg() -> tuple[str, str]:
    url = os.environ.get("LEX_AGENT_SUPABASE_URL", "").strip()
    key = os.environ.get("LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        sys.stderr.write(
            "Defina LEX_AGENT_SUPABASE_URL e LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY "
            "(ou aplique sql/import_cursos_flashcards_to_lex.sql no Supabase).\n"
        )
        sys.exit(1)
    return url.rstrip("/"), key


def import_via_rest(base: str, key: str) -> tuple[int, int]:
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept-Profile": "lex",
        "Content-Profile": "lex",
        "Prefer": "return=minimal",
    }
    pub_headers = {**headers, "Accept-Profile": "public", "Content-Profile": "public"}

    with httpx.Client(timeout=120.0) as client:
        # Limpa destino lex
        client.delete(f"{base}/rest/v1/flashcards?id=not.is.null", headers=headers)
        client.delete(f"{base}/rest/v1/flashcard_decks?id=not.is.null", headers=headers)

        deck_rows = [
            {"slug": s, "name": n, "category": c, "sort_order": i} for s, n, c, i in DECKS
        ]
        res = client.post(
            f"{base}/rest/v1/flashcard_decks",
            headers={**headers, "Prefer": "return=representation"},
            json=deck_rows,
        )
        res.raise_for_status()
        decks = {d["name"]: d["id"] for d in res.json()}

        offset = 0
        limit = 500
        total_cards = 0
        sort_counters: dict[str, int] = {}

        while True:
            src = client.get(
                f"{base}/rest/v1/flashcards"
                f"?select=id,discipline,front,back,created_at"
                f"&order=discipline.asc,created_at.asc&limit={limit}&offset={offset}",
                headers=pub_headers,
            )
            src.raise_for_status()
            batch = src.json()
            if not batch:
                break

            payload = []
            for row in batch:
                deck_id = decks.get(row["discipline"])
                if not deck_id:
                    continue
                sort_counters[deck_id] = sort_counters.get(deck_id, 0) + 1
                back = row.get("back") or ""
                highlight = None
                if "<mark>" in back:
                    import re

                    m = re.search(r"<mark>([^<]+)</mark>", back)
                    if m:
                        highlight = m.group(1)
                payload.append(
                    {
                        "deck_id": deck_id,
                        "front": row["front"],
                        "back": back,
                        "highlight": highlight,
                        "sort_order": sort_counters[deck_id],
                    }
                )

            if payload:
                ins = client.post(f"{base}/rest/v1/flashcards", headers=headers, json=payload)
                ins.raise_for_status()
                total_cards += len(payload)

            if len(batch) < limit:
                break
            offset += limit

    return len(decks), total_cards


def main() -> int:
    if SQL.is_file() and os.environ.get("LEX_FLASHCARDS_IMPORT_USE_SQL") == "1":
        print(f"Aplique manualmente: {SQL}")
        return 0
    base, key = _cfg()
    decks, cards = import_via_rest(base, key)
    print(f"Importados {cards} flashcards em {decks} decks (lex schema)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
