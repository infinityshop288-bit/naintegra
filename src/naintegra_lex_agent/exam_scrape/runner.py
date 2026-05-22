"""Orquestra harvest Playwright particionado por banca/cargo e grava JSONL bruto."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..concurso_study.playwright_capture import cmd_playwright_harvest_url_plan
from ..concurso_study.settings import QConcursoStudySettings, load_qc_study_settings
from ..settings import Settings
from .targets import slug_board, slug_cargo
from .url_plan import build_full_plan, slice_plan

logger = logging.getLogger(__name__)


def _parse_sources(s: str) -> tuple[str, ...]:
    return tuple(x.strip().lower() for x in s.split(",") if x.strip())


def exam_scrape_offset_path(settings: Settings) -> Path:
    return Path(settings.exam_scrape_state_dir) / "exam_scrape_offset.txt"


def read_rotate_offset(settings: Settings) -> int:
    p = exam_scrape_offset_path(settings)
    if not p.is_file():
        return 0
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except ValueError:
        return 0


def write_rotate_offset(settings: Settings, offset: int) -> None:
    p = exam_scrape_offset_path(settings)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(offset), encoding="utf-8")


def append_partitioned(inbox: Path, records: list[dict[str, Any]]) -> None:
    """Grava por ``inbox/<BANCA>/<cargo_slug>.jsonl`` para revisão antes do Lex."""

    for rec in records:
        banca = str(rec.get("banca") or rec.get("organizadora") or "SEM_BANCA").strip().upper()
        cargo = str(rec.get("cargo_alvo") or rec.get("cargo") or "sem_cargo").strip()
        sub = inbox / slug_board(banca)
        sub.mkdir(parents=True, exist_ok=True)
        dest = sub / f"{slug_cargo(cargo)}.jsonl"
        with dest.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run_exam_board_scrape_batch(settings: Settings) -> tuple[int, int]:
    """Um lote rotativo de URLs; retorna (exit_code, linhas_gravadas_particionadas)."""

    sources = _parse_sources(settings.exam_scrape_sources)
    full = build_full_plan(include_official=settings.exam_scrape_include_official, sources=sources)
    if not full:
        logger.warning("exam_scrape: plano vazio (fontes=%s)", sources)
        return 0, 0

    offset = read_rotate_offset(settings)
    batch = slice_plan(full, offset=offset, limit=int(settings.exam_scrape_pairs_per_cycle))
    next_offset = (offset + len(batch)) % len(full)
    write_rotate_offset(settings, next_offset)

    qc: QConcursoStudySettings = load_qc_study_settings()
    st_path = qc.playwright_storage_state_path
    st_exist = st_path if st_path.is_file() else None

    pairs: list[tuple[str, dict[str, Any]]] = [(nav.url, dict(nav.tags)) for nav in batch]

    inbox = Path(settings.exam_scrape_inbox_path).resolve()
    inbox.mkdir(parents=True, exist_ok=True)

    def partition_sink(rows: list[dict[str, Any]]) -> None:
        append_partitioned(inbox, rows)

    code, n_network = cmd_playwright_harvest_url_plan(
        settings=qc,
        state_path=st_exist,
        url_tag_pairs=pairs,
        headed=settings.exam_scrape_headed,
        seconds_per_url=float(settings.exam_scrape_seconds_per_url),
        url_substring=(settings.exam_scrape_url_substring or "").strip(),
        emit_if_wrong_unknown=settings.scrape_harvest_emit_unknown_wrong,
        harvest_emit_mode=settings.scrape_harvest_emit_mode,
        partition_sink=partition_sink,
        source_note=qc.qconcurso_base_url.rstrip("/") + "/",
    )
    return code, n_network
