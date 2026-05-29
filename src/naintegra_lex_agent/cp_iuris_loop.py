"""Loop contínuo: extrai CP IURIS 2025 (PDF + Ollama) até esgotar a fila."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from .cp_iuris_extract import run_extraction_batch

logger = logging.getLogger("naintegra_lex_agent.cp_iuris_loop")

_stop = False


def _on_signal(_signo: int, _frame: object | None) -> None:
    global _stop
    _stop = True
    logger.info("Interrupção solicitada; encerrando após o ciclo atual.")


def default_pdf_dirs() -> list[Path]:
    home = Path.home()
    candidates = [
        home / "Downloads",
        Path(__file__).resolve().parents[2] / "data" / "cp_iuris_2025" / "pdfs",
    ]
    return [p for p in candidates if p.is_dir()]


def run_loop(
    *,
    pdf_dirs: list[Path],
    output_dir: Path,
    chunks_per_cycle: int = 16,
    parallel_workers: int = 3,
    page_chars: int = 2400,
    poll_interval_seconds: float = 0.0,
    delay_seconds: float = 0.0,
    max_cycles: int | None = None,
) -> int:
    global _stop
    _stop = False
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    cycle = 0
    while not _stop:
        cycle += 1
        if max_cycles is not None and cycle > max_cycles:
            logger.info("Limite de ciclos atingido (%s).", max_cycles)
            break

        processed, pending_before, total, finished = run_extraction_batch(
            pdf_dirs=pdf_dirs,
            output_dir=output_dir,
            chunks_per_batch=chunks_per_cycle,
            parallel_workers=parallel_workers,
            page_chars=page_chars,
            delay_seconds=delay_seconds,
        )

        if total == 0:
            logger.error("Nenhum material indexado; verifique os PDFs em %s", pdf_dirs)
            return 1

        if finished:
            note = output_dir / "terminei.txt"
            note.write_text(
                f"Extração CP IURIS 2025 concluída.\n"
                f"Chunks: {total}\n"
                f"Saída: {output_dir / 'knowledge.jsonl'}\n"
                f"Corpus Lex: {output_dir / 'corpus.jsonl'}\n",
                encoding="utf-8",
            )
            print(
                f"\n{'=' * 72}\n"
                f"CP IURIS 2025 — extração concluída ({total} trechos).\n"
                f" knowledge.jsonl → {output_dir / 'knowledge.jsonl'}\n"
                f" corpus.jsonl    → {output_dir / 'corpus.jsonl'}\n"
                f"{'=' * 72}\n",
                file=sys.stderr,
                flush=True,
            )
            return 0

        if processed == 0 and pending_before > 0:
            wait = poll_interval_seconds if poll_interval_seconds > 0 else 5.0
            logger.info(
                "Ciclo %s: nada processado (Ollama offline ou falhas). Repetindo em %ss…",
                cycle,
                wait,
            )
        else:
            remaining = max(0, pending_before - processed)
            logger.info(
                "Ciclo %s: +%s trechos · restam ~%s de %s · workers %s",
                cycle,
                processed,
                remaining,
                total,
                parallel_workers,
            )

        if _stop:
            break

        if processed > 0 and poll_interval_seconds <= 0:
            continue

        wait = poll_interval_seconds if poll_interval_seconds > 0 else (
            5.0 if processed == 0 else 0.0
        )
        if wait <= 0:
            continue

        slept = 0.0
        while slept < wait and not _stop:
            time.sleep(min(1.0, wait - slept))
            slept += 1.0

    logger.info("Loop interrompido pelo usuário.")
    return 130


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Extrai conhecimento jurídico dos e-books CP IURIS 2025 com Ollama (loop até o fim)."
    )
    parser.add_argument(
        "--pdf-dir",
        action="append",
        type=Path,
        default=None,
        help="Pasta com PDFs IURIS 2025 (repita para várias). Default: ~/Downloads.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo / "data" / "cp_iuris_2025",
        help="Pasta de saída (knowledge.jsonl, corpus.jsonl, state.json).",
    )
    parser.add_argument(
        "--chunks-per-cycle",
        type=int,
        default=int(__import__("os").environ.get("CP_IURIS_CHUNKS_PER_CYCLE", "16")),
        help="Trechos processados por ciclo.",
    )
    parser.add_argument(
        "--parallel-workers",
        type=int,
        default=int(__import__("os").environ.get("CP_IURIS_PARALLEL_WORKERS", "3")),
        help="Chamadas Ollama em paralelo por lote.",
    )
    parser.add_argument("--page-chars", type=int, default=2400)
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(__import__("os").environ.get("CP_IURIS_POLL_INTERVAL_SECONDS", "0")),
        help="Pausa entre ciclos (0 = imediato quando há progresso).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=float(__import__("os").environ.get("CP_IURIS_DELAY_SECONDS", "0")),
        help="Pausa entre chamadas Ollama (0 = sem pausa).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Um único lote e sai (sem loop).",
    )
    parser.add_argument("--max-cycles", type=int, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    pdf_dirs = [p.expanduser().resolve() for p in (args.pdf_dir or default_pdf_dirs())]
    output_dir = args.output_dir.expanduser().resolve()

    if args.once:
        processed, pending, total, finished = run_extraction_batch(
            pdf_dirs=pdf_dirs,
            output_dir=output_dir,
            chunks_per_batch=args.chunks_per_cycle,
            parallel_workers=args.parallel_workers,
            page_chars=args.page_chars,
            delay_seconds=args.delay,
        )
        print(f"Lote: +{processed} · pendentes antes {pending} · total {total} · fim={finished}")
        return 0 if total > 0 else 1

    return run_loop(
        pdf_dirs=pdf_dirs,
        output_dir=output_dir,
        chunks_per_cycle=args.chunks_per_cycle,
        parallel_workers=args.parallel_workers,
        page_chars=args.page_chars,
        poll_interval_seconds=args.poll_interval,
        delay_seconds=args.delay,
        max_cycles=args.max_cycles,
    )


def main_sync() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    main_sync()
