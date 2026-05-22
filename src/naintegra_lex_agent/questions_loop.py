"""Loop contínuo: scraping Playwright (JSON na rede) → fusão no corpus → Lex normalize/manifest.

Use com Playwright instalado e sessão QConcurso (QC_STUDY_PLAYWRIGHT_STORAGE_STATE_PATH).
Recomendado: LEX_AGENT_SCRAPE_LOOP_MODE=playwright_harvest e
LEX_AGENT_SCRAPE_HARVEST_EMIT_MODE=all_with_gabarito para objetivas/discursivas com gabarito.

Cada ciclo: ``run_scrape_cycle`` (se o modo não for ``off``) e em seguida ``collect_cycle``
(mesmos destinos que organize-loop: organized, opcional ``data/analyzed``, opcional ``repository/``, preview).
Atualiza também ``preview/evolucao-organizacao.html`` com o histórico por ciclo.
O bloco de notas ``terminei`` só abre ao encerrar sem interrupção, último ciclo OK e sem truncagem
(``len(rows) < LEX_AGENT_MAX_RECORDS_PER_CYCLE``), ou use ``LEX_AGENT_QUESTIONS_LOOP_IDLE_CYCLES_BEFORE_EXIT`` para sair com fila vazia.
Intervalo entre ciclos: ``LEX_AGENT_QUESTIONS_LOOP_INTERVAL_SECONDS``.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
from typing import Any

from .agent import _configure_logging, collect_cycle
from .concurso_study.settings import load_qc_study_settings
from .material_merge import settings_with_trilhante_informativo_root
from .organize_loop import apply_loop_defaults, emit_local_loop_finished_banner
from .preview_evolution import (
    maybe_open_terminei_completion_note,
    refresh_organize_preview_after_cycle,
)
from .scrape_loop import run_scrape_cycle, write_scrape_status
from .settings import Settings, load_settings

logger = logging.getLogger("naintegra_lex_agent.questions_loop")


def ensure_qc_inbox_merge(settings: Settings) -> Settings:
    """Inclui a inbox QConcurso na fusão material→corpus (harvest grava lá por padrão)."""

    qc_root = str(load_qc_study_settings().qconcurso_inbox_path.resolve())
    roots = [r.strip() for r in settings.material_merge_extra_roots.split(",") if r.strip()]
    if qc_root not in roots:
        roots.append(qc_root)
    return settings.model_copy(update={"material_merge_extra_roots": ",".join(roots)})


def ensure_exam_scrape_merge(settings: Settings) -> Settings:
    exam_root = str(settings.exam_scrape_inbox_path.resolve())
    roots = [r.strip() for r in settings.material_merge_extra_roots.split(",") if r.strip()]
    if exam_root not in roots:
        roots.append(exam_root)
    return settings.model_copy(update={"material_merge_extra_roots": ",".join(roots)})


def apply_questions_loop_settings(settings: Settings) -> Settings:
    organized = apply_loop_defaults(settings)
    organized = ensure_qc_inbox_merge(organized)
    organized = ensure_exam_scrape_merge(organized)
    return settings_with_trilhante_informativo_root(organized)


def main_sync() -> None:
    settings = apply_questions_loop_settings(load_settings())
    _configure_logging(settings.log_level)

    stop = threading.Event()

    def _stop(*_: object) -> None:
        logger.info("Encerrando questions-loop (sinal)...")
        stop.set()

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    cycles = 0
    scrape_ok = 0
    last_scrape_exit: int | None = None
    idle_count = 0
    last_cycle_row_count: int | None = None
    last_cycle_failed = False

    if settings.scrape_harvest_emit_mode != "all_with_gabarito":
        logger.warning(
            "LEX_AGENT_SCRAPE_HARVEST_EMIT_MODE=%s — para capturar objetivas com gabarito e discursivas "
            "com resposta modelo, use all_with_gabarito.",
            settings.scrape_harvest_emit_mode,
        )

    logger.info(
        "NaIntegra questions-loop — scrape=%s emit=%s organize inbox=%s merge_roots=%s "
        "intervalo_entre_ciclos=%ss (LEX_AGENT_QUESTIONS_LOOP_INTERVAL_SECONDS) run_once=%s "
        "idle_exit_after=%s analisado enabled=%s path=%s",
        settings.scrape_loop_mode,
        settings.scrape_harvest_emit_mode,
        settings.crawl_inbox_path,
        settings.material_merge_extra_roots,
        settings.questions_loop_interval_seconds,
        settings.questions_loop_run_once,
        settings.questions_loop_idle_cycles_before_exit,
        settings.analyzed_output_enabled,
        settings.analyzed_output_path,
    )

    while not stop.is_set():
        cycles += 1
        n_scrape = 0
        rows: list[dict[str, Any]] = []
        cycle_err: str | None = None
        try:
            if settings.scrape_loop_mode != "off":
                code, msg, n_scrape = run_scrape_cycle(settings)
                last_scrape_exit = code
                if code == 0:
                    scrape_ok += 1
                write_scrape_status(
                    settings.scrape_status_path,
                    job=settings.scrape_job_name,
                    done=scrape_ok,
                    total=cycles,
                    message=msg,
                    exit_code=code,
                    mode=settings.scrape_loop_mode,
                    records_written=n_scrape if n_scrape > 0 else None,
                )
            rows = collect_cycle(settings)
            logger.info(
                "questions-loop ciclo %s — scrape_exit=%s último_jsonl=%s docs_normalizados=%s; próximo ciclo em %ss",
                cycles,
                last_scrape_exit,
                n_scrape,
                len(rows),
                settings.questions_loop_interval_seconds,
            )
        except Exception:
            logger.exception("questions-loop: falha no ciclo %s", cycles)
            cycle_err = "exceção no ciclo questions-loop (ver logs)"
            if settings.scrape_loop_mode != "off":
                write_scrape_status(
                    settings.scrape_status_path,
                    job=settings.scrape_job_name,
                    done=scrape_ok,
                    total=cycles,
                    message="exceção no ciclo questions-loop (ver logs)",
                    exit_code=-1,
                    mode=settings.scrape_loop_mode,
                )
        refresh_organize_preview_after_cycle(
            settings,
            loop_name="questions-loop",
            cycle=cycles,
            rows=rows,
            error=cycle_err,
        )

        last_cycle_row_count = len(rows)
        last_cycle_failed = cycle_err is not None
        if cycle_err:
            idle_count = 0
        elif len(rows) == 0:
            idle_count += 1
        else:
            idle_count = 0
        threshold = settings.questions_loop_idle_cycles_before_exit
        if threshold > 0 and cycle_err is None and idle_count >= threshold:
            logger.info(
                "questions-loop: %s ciclos seguidos sem novos documentos — encerrando (fila vazia).",
                threshold,
            )
            break

        if settings.questions_loop_run_once:
            logger.info("questions-loop run_once — encerrando após um ciclo.")
            break

        if stop.wait(timeout=float(settings.questions_loop_interval_seconds)):
            break

    logger.info("questions-loop encerrado (%s ciclos)", cycles)
    emit_local_loop_finished_banner("questions-loop", settings, cycles=cycles)
    maybe_open_terminei_completion_note(
        settings,
        interrupted_by_signal=stop.is_set(),
        last_cycle_row_count=last_cycle_row_count,
        last_cycle_failed=last_cycle_failed,
        cycles_executed=cycles,
    )
    sys.exit(0)


def main() -> None:
    main_sync()


if __name__ == "__main__":
    main_sync()
