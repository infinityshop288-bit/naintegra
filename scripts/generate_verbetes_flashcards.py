#!/usr/bin/env python3
"""Gera flashcards a partir de DOCX de verbetes e publica no NaIntegra Lex (Supabase schema lex)."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from naintegra_lex_agent.flashcards_from_docx import run_flashcards_pipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "docx",
        type=Path,
        help="Arquivo .docx com verbetes (ex.: Cópia de verbetes - je - jf - df).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO / "data" / "flashcards_verbetes",
        help="Pasta para cards.jsonl e state.json (retomável).",
    )
    parser.add_argument("--page-chars", type=int, default=2800, help="Tamanho alvo de cada página.")
    parser.add_argument("--min-cards", type=int, default=2, help="Mínimo de flashcards por página.")
    parser.add_argument(
        "--ai-mode",
        choices=("classify", "generate"),
        default="classify",
        help="classify=heurística+IA disciplina (rápido) | generate=IA gera conteúdo (lento).",
    )
    parser.add_argument(
        "--publish-batch-pages",
        type=int,
        default=25,
        help="Publica no Supabase a cada N páginas processadas.",
    )
    parser.add_argument("--max-pages", type=int, default=None, help="Limite de páginas (teste).")
    parser.add_argument("--dry-run", action="store_true", help="Não grava no Supabase.")
    parser.add_argument(
        "--jsonl-only",
        action="store_true",
        help="Só gera cards.jsonl (sem publicar no Supabase).",
    )
    parser.add_argument(
        "--export-catalog",
        action="store_true",
        default=True,
        help="Ao final, exporta web/lex/data/flashcards.json.",
    )
    parser.add_argument("--no-export-catalog", action="store_false", dest="export_catalog")
    parser.add_argument("--delay", type=float, default=0.0, help="Pausa entre lotes de IA (segundos).")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    docx = args.docx.expanduser().resolve()
    if not docx.is_file():
        sys.stderr.write(f"Arquivo não encontrado: {docx}\n")
        return 1

    state = run_flashcards_pipeline(
        docx_path=docx,
        output_dir=args.output_dir.resolve(),
        page_chars=args.page_chars,
        min_cards_per_page=args.min_cards,
        ai_mode=args.ai_mode,
        publish_batch_pages=args.publish_batch_pages,
        max_pages=args.max_pages,
        dry_run=args.dry_run or args.jsonl_only,
        delay_seconds=args.delay,
    )

    print(
        f"Concluído: {state.processed_pages}/{state.total_pages} páginas · "
        f"{state.generated_cards} cards gerados · {state.published_cards} publicados no lex."
    )

    if not args.dry_run and not args.jsonl_only:
        note = args.output_dir / "terminei.txt"
        note.write_text(
            f"Flashcards verbetes concluídos em {state.updated_at}\n"
            f"Páginas: {state.processed_pages}/{state.total_pages}\n"
            f"Cards publicados nesta execução: {state.published_cards}\n",
            encoding="utf-8",
        )
        print(f"Aviso gravado em {note}")

    if args.export_catalog and not args.dry_run:
        export_script = REPO / "scripts" / "export_lex_flashcards_catalog.py"
        if export_script.is_file():
            subprocess.run([sys.executable, str(export_script)], check=False)

    return 0


if __name__ == "__main__":
    sys.exit(main())
