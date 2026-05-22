#!/usr/bin/env python3
"""Gera flashcards a partir de PDFs (provas comentadas / material de aula) e publica no NaIntegra Lex."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from naintegra_lex_agent.flashcards_from_docx import (  # noqa: E402
    load_pdf_folder_pages,
    paginate_text_pages,
    run_flashcards_pipeline_from_pdf_folder,
)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pdf_dir",
        type=Path,
        help="Pasta com PDFs (provas comentadas, material de aula).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO / "data" / "flashcards_provas",
        help="Pasta para cards.jsonl e state.json (retomável).",
    )
    parser.add_argument("--page-chars", type=int, default=2800)
    parser.add_argument("--min-cards", type=int, default=2)
    parser.add_argument("--ai-mode", choices=("classify", "generate"), default="classify")
    parser.add_argument("--publish-batch-pages", type=int, default=40)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--jsonl-only", action="store_true")
    parser.add_argument("--no-dedupe", action="store_true", help="Processa PDFs duplicados (1).pdf")
    parser.add_argument("--export-catalog", action="store_true", default=True)
    parser.add_argument("--no-export-catalog", action="store_false", dest="export_catalog")
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    pdf_dir = args.pdf_dir.expanduser().resolve()
    if not pdf_dir.is_dir():
        sys.stderr.write(f"Pasta não encontrada: {pdf_dir}\n")
        return 1

    raw = load_pdf_folder_pages(pdf_dir, dedupe=not args.no_dedupe)
    entries = paginate_text_pages(raw, args.page_chars)
    print(f"PDFs: {len(list(pdf_dir.glob('*.pdf')))} arquivos · {len(raw)} páginas · {len(entries)} pseudo-páginas")

    state = run_flashcards_pipeline_from_pdf_folder(
        folder_path=pdf_dir,
        output_dir=args.output_dir.resolve(),
        page_chars=args.page_chars,
        min_cards_per_page=args.min_cards,
        ai_mode=args.ai_mode,
        publish_batch_pages=args.publish_batch_pages,
        max_pages=args.max_pages,
        dry_run=args.dry_run or args.jsonl_only,
        delay_seconds=args.delay,
        dedupe_pdfs=not args.no_dedupe,
    )

    print(
        f"Concluído: {state.processed_pages}/{state.total_pages} páginas · "
        f"{state.generated_cards} cards · {state.published_cards} publicados no lex."
    )

    if not args.dry_run and not args.jsonl_only:
        note = args.output_dir / "terminei.txt"
        note.write_text(
            f"Flashcards provas concluídos em {state.updated_at}\n"
            f"Páginas: {state.processed_pages}/{state.total_pages}\n"
            f"Cards publicados: {state.published_cards}\n",
            encoding="utf-8",
        )
        print(f"Aviso gravado em {note}")

    if args.export_catalog and not args.dry_run and not args.jsonl_only:
        export_script = REPO / "scripts" / "export_lex_flashcards_catalog.py"
        if export_script.is_file():
            subprocess.run([sys.executable, str(export_script)], check=False)

    return 0


if __name__ == "__main__":
    sys.exit(main())
