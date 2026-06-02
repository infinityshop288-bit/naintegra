#!/usr/bin/env python3
"""Reprocessa trechos CP IURIS que falharam (abandonados no log ou ausentes do knowledge.jsonl)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from naintegra_lex_agent.cp_iuris_extract import (  # noqa: E402
    collect_abandoned_chunk_ids,
    load_done_chunk_ids,
    retry_failed_extractions,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(REPO / "data" / "cp_iuris_2025" / "extraction.log", encoding="utf-8"),
    ],
)


def main() -> int:
    output_dir = REPO / "data" / "cp_iuris_2025"
    abandoned = collect_abandoned_chunk_ids(
        output_dir / "extraction.log",
        output_dir / "chunks_index.json",
    )
    done = load_done_chunk_ids(output_dir / "knowledge.jsonl")
    missing = [cid for cid in abandoned if cid not in done]

    if missing:
        print(f"Trechos ausentes: {len(missing)}")
        targets = missing
    elif abandoned:
        print(f"Reextrair {len(abandoned)} trechos que falharam persistentemente no log")
        targets = abandoned
    else:
        print("Nenhum trecho para retry.")
        return 0

    recovered, still = retry_failed_extractions(
        output_dir=output_dir,
        chunk_ids=targets,
        chunks_per_batch=min(4, len(targets)),
        parallel_workers=1,
    )
    print(f"Recuperados nesta execução: {recovered}")
    if still:
        print(f"Ainda pendentes/falhas: {still}")
        return 1
    print("Retry concluído com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
