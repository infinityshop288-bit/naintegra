#!/usr/bin/env python3
"""Indexa e extrai FGV em Teses / Plano MP 2024 (PDF+DOCX) com Ollama."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from naintegra_lex_agent.study_material_extract import (  # noqa: E402
    index_study_material,
    run_study_extraction_batch,
)

DEFAULT_SOURCES = {
    "fgv_em_teses": Path("/Users/luizcarlos/Downloads/FGV em TESES"),
    "plano_mp_2024": Path("/Users/luizcarlos/Downloads/Plano Completo - MP 2024"),
}


def parse_sources(raw: list[str] | None) -> dict[str, Path]:
    if not raw:
        return {k: v for k, v in DEFAULT_SOURCES.items() if v.is_dir()}
    out: dict[str, Path] = {}
    for item in raw:
        if ":" not in item:
            raise SystemExit(f"Formato inválido (use corpus:/caminho): {item}")
        corpus, path = item.split(":", 1)
        corpus = corpus.strip()
        path = path.strip()
        if not corpus:
            raise SystemExit(f"Corpus vazio em: {item}")
        out[corpus] = Path(path).expanduser()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        action="append",
        default=None,
        help="corpus:/pasta (ex.: fgv_em_teses:~/Downloads/FGV em TESES). Repita.",
    )
    parser.add_argument(
        "--output-base",
        type=Path,
        default=REPO / "data" / "study_materials",
        help="Base de saída; cada corpus em <base>/<corpus>/",
    )
    parser.add_argument("--index-only", action="store_true", help="Só indexa PDFs/DOCX.")
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Reconstrói chunks_index.json mesmo se já existir.",
    )
    parser.add_argument("--once", action="store_true", help="Um lote por corpus e sai.")
    parser.add_argument(
        "--chunks-per-cycle",
        type=int,
        default=int(os.environ.get("STUDY_CHUNKS_PER_CYCLE", "12")),
    )
    parser.add_argument(
        "--parallel-workers",
        type=int,
        default=int(os.environ.get("STUDY_PARALLEL_WORKERS", "2")),
    )
    parser.add_argument("--max-cycles", type=int, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,
    )
    for h in logging.root.handlers:
        h.flush = getattr(h, "flush", lambda: None)  # type: ignore[method-assign]

    sources = parse_sources(args.source)
    if not sources:
        print("Nenhuma pasta de origem encontrada.", file=sys.stderr)
        return 1

    for corpus, root in sources.items():
        if not root.is_dir():
            print(f"Pasta não encontrada ({corpus}): {root}", file=sys.stderr)
            return 1
        out = (args.output_base / corpus).resolve()
        index_path = out / "chunks_index.json"
        if args.reindex or not index_path.is_file():
            index_study_material(input_roots=[root], output_dir=out, corpus=corpus)
        else:
            logging.info("Índice existente: %s (use --reindex para recriar)", index_path)

    if args.index_only:
        return 0

    cycle = 0
    while True:
        cycle += 1
        if args.max_cycles is not None and cycle > args.max_cycles:
            break
        any_pending = False
        for corpus in sources:
            out = (args.output_base / corpus).resolve()
            processed, pending_before, total, finished = run_study_extraction_batch(
                output_dir=out,
                corpus=corpus,
                chunks_per_batch=args.chunks_per_cycle,
                parallel_workers=args.parallel_workers,
            )
            if total == 0:
                continue
            if not finished and pending_before > 0:
                any_pending = True
            if finished:
                (out / "terminei.txt").write_text(
                    f"Extração {corpus} concluída.\nTrechos: {total}\n",
                    encoding="utf-8",
                )

        if args.once:
            break
        if not any_pending:
            logging.info("Todos os corpora concluídos.")
            break

        logging.info("Ciclo %s concluído; próximo lote imediato.", cycle)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logging.info("Interrompido pelo usuário.")
        raise SystemExit(130)
    except Exception:
        logging.exception("Extração encerrada com erro fatal")
        raise SystemExit(1)
