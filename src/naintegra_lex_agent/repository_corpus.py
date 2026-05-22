"""Corpus Lex versionável no próprio clone do NaIntegra (JSONL mesclado por ``external_id``)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def merge_rows_into_repository_corpus(path: Path | str, rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Acrescenta ou atualiza registros no arquivo único do repositório.

    Retorna ``(total_de_external_ids_no_arquivo, len(rows))`` após gravação.
    Mesmo esquema de ``NormalizedDocument.row_for_supabase()`` (compatível com ``lex.ingested_documents``).
    """

    if not rows:
        return 0, 0

    dest = Path(path).expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    if dest.is_file():
        raw_lines = dest.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(raw_lines, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("repository corpus: linha %s ignorada (JSON inválido) em %s", lineno, dest)
                continue
            eid = obj.get("external_id")
            if not eid:
                logger.warning("repository corpus: linha %s sem external_id — ignorada", lineno)
                continue
            eid_s = str(eid).strip()
            if not eid_s:
                continue
            if eid_s not in by_id:
                order.append(eid_s)
            by_id[eid_s] = obj

    for row in rows:
        eid_s = str(row.get("external_id") or "").strip()
        if not eid_s:
            logger.warning("repository corpus: registro sem external_id — ignorado")
            continue
        if eid_s not in by_id:
            order.append(eid_s)
        by_id[eid_s] = row

    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for eid in order:
            fh.write(json.dumps(by_id[eid], ensure_ascii=False) + "\n")
    tmp.replace(dest)

    logger.info(
        "Repositório corpus atualizado — %s documentos únicos (%s neste ciclo) → %s",
        len(order),
        len(rows),
        dest,
    )
    return len(order), len(rows)
