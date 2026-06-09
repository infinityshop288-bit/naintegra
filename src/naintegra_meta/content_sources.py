"""Fontes Lex/flashcards para pauta diária."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
FLASHCARD_CATALOG = REPO / "web" / "lex" / "data" / "flashcards_catalog.json"
DECKS_DIR = REPO / "web" / "lex" / "data" / "flashcards" / "decks"

PENAL_DECKS = (
    "dir-penal-geral",
    "dir-penal-especial",
    "dir-proc-penal",
    "jurisprudencia",
    "dir-const",
    "dir-adm",
)


def _load_deck(slug: str) -> list[dict[str, Any]]:
    path = DECKS_DIR / f"{slug}.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    cards = data.get("cards") or data.get("flashcards") or []
    if isinstance(cards, list):
        return [c for c in cards if isinstance(c, dict)]
    return []


def pick_flashcard_context(
    *,
    deck_slug: str | None = None,
    discipline_hint: str | None = None,
) -> dict[str, str]:
    slug = deck_slug
    if not slug:
        if discipline_hint:
            hint = discipline_hint.lower()
            if "process" in hint or "cpp" in hint:
                slug = "dir-proc-penal"
            elif "const" in hint:
                slug = "dir-const"
            elif "adm" in hint or "edital" in hint:
                slug = "dir-adm"
            else:
                slug = random.choice(PENAL_DECKS)
        else:
            slug = random.choice(PENAL_DECKS)

    cards = _load_deck(slug)
    if not cards:
        return {
            "deck_slug": slug,
            "tema": "Direito Penal — revisão para concurso policial",
            "contexto": "Sem flashcard no acervo; use conceito clássico de tipicidade e dolo.",
        }

    card = random.choice(cards)
    front = str(card.get("front") or card.get("pergunta") or "").strip()
    back = str(card.get("back") or card.get("resposta") or "").strip()
    tema = front[:220] if front else slug.replace("-", " ")
    contexto = back[:3500] if back else front
    return {"deck_slug": slug, "tema": tema, "contexto": contexto}
