"""Loop contínuo: funde JSONL de várias fontes, organiza e atualiza o manifest (preview opcional).

A cada iteração chama ``collect_cycle`` (fusão → normalização → manifest em ``LEX_AGENT_ORGANIZED_OUTPUT_PATH`` e,
se ``LEX_AGENT_ANALYZED_OUTPUT_ENABLED=true``, cópia equivalente em ``LEX_AGENT_ANALYZED_OUTPUT_PATH``).

Sem credenciais Supabase, ``apply_loop_defaults`` liga ``LEX_AGENT_ANALYZED_OUTPUT_ENABLED`` para gravar também
``data/analyzed`` (legislação/jurisprudência categorizadas neste dispositivo).

Defina ``LEX_AGENT_TRILHANTE_INFORMATIVO_ROOT`` (ex.: ``./output_trilhante_informativo``) para fundir JSONL de
jurisprudência, súmulas e legislação produzidos pelo pipeline Trilhante — mesmo critério que ``material_merge_extra_roots``.

Opcional: ``LEX_AGENT_REPOSITORY_CORPUS_ENABLED=true`` grava/atualiza ``repository/lex_corpus.jsonl``
(no clone NaIntegra) com o mesmo registro enviado ao Supabase.

Intervalo entre ciclos: ``LEX_AGENT_POLL_INTERVAL_SECONDS`` (``stop.wait`` ao fim de cada volta).

A cada ciclo atualiza ``preview/evolucao-organizacao.html`` (evolução por volume e tipo).

O bloco de notas ``preview/terminei.txt`` só abre quando o loop termina **sem Ctrl+C/SIGTERM**, o último ciclo
foi bem-sucedido e normalizou **menos** documentos que ``LEX_AGENT_MAX_RECORDS_PER_CYCLE`` (sem truncagem —
material da volta atual inteira). Para encerrar após fila vazia sem interromper, use
``LEX_AGENT_ORGANIZE_LOOP_IDLE_CYCLES_BEFORE_EXIT`` (> 0).

Sem upsert Supabase neste comando — apenas disco local.
Um ciclo e saída: ``LEX_AGENT_RUN_ONCE=true`` com ``naintegra-organize-loop``.
``LEX_AGENT_DRY_RUN=true`` também impede gravação em ``repository/lex_corpus.jsonl`` e na pasta analisada.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
from typing import Any

from .agent import _configure_logging, collect_cycle
from .material_merge import settings_with_trilhante_informativo_root
from .preview_evolution import (
    maybe_open_terminei_completion_note,
    refresh_organize_preview_after_cycle,
)
from .settings import Settings, load_settings

logger = logging.getLogger("naintegra_lex_agent.organize_loop")


def emit_local_loop_finished_banner(
    loop_name: str, settings: Settings, *, cycles: int | None = None
) -> None:
    """Aviso visível ao encerrar o loop (stderr), para supervisão local."""

    lines = [
        "",
        "=" * 72,
        f"NaIntegra Lex — loop «{loop_name}» encerrado.",
    ]
    if cycles is not None:
        lines.append(f"Ciclos executados: {cycles}.")
    paths = [
        f"Manifestos organizados: {settings.organized_output_path.resolve()}",
        f"Análise/categorização (se habilitada): {settings.analyzed_output_path.resolve()}",
        f"Corpus no repositório (se habilitado): {settings.repository_corpus_path.resolve()}",
    ]
    if settings.preview_evolution_enabled:
        paths.insert(
            0,
            f"Preview evolução (HTML): {settings.preview_evolution_html_path.resolve()}",
        )
    lines.extend(paths + ["=" * 72, ""])
    print("\n".join(lines), file=sys.stderr, flush=True)


def apply_organize_merge_roots(settings: Settings) -> Settings:
    """Inclui inbox QConcurso e ``exam_scrape`` na fusão (sem depender de ``questions_loop``)."""

    from .concurso_study.settings import load_qc_study_settings

    roots = [r.strip() for r in settings.material_merge_extra_roots.split(",") if r.strip()]
    qc_root = str(load_qc_study_settings().qconcurso_inbox_path.resolve())
    exam_root = str(settings.exam_scrape_inbox_path.resolve())
    for extra in (qc_root, exam_root):
        if extra not in roots:
            roots.append(extra)
    return settings.model_copy(update={"material_merge_extra_roots": ",".join(roots)})


def apply_loop_defaults(settings: Settings) -> Settings:
    """Fusão + pasta estável de organização; sem Supabase, garante sink ``data/analyzed``."""

    oid = (settings.organized_batch_id or "").strip() or "latest"
    updates: dict[str, object] = {
        "material_merge_before_cycle": True,
        "organized_batch_id": oid,
        "sync_preview_manifest": True,
    }
    if not settings.has_supabase_credentials():
        updates["analyzed_output_enabled"] = True
    return settings.model_copy(update=updates)


def main_sync() -> None:
    settings = settings_with_trilhante_informativo_root(
        apply_organize_merge_roots(apply_loop_defaults(load_settings()))
    )
    _configure_logging(settings.log_level)

    stop = threading.Event()

    def _stop(*_: object) -> None:
        logger.info("Encerrando organize-loop (sinal)...")
        stop.set()

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    logger.info(
        "NaIntegra organize-loop — inbox=%s fusão=%s organized_batch=%s "
        "intervalo_entre_ciclos=%ss (LEX_AGENT_POLL_INTERVAL_SECONDS) run_once=%s dry_run=%s "
        "idle_exit_after=%s ciclos analisado path=%s enabled=%s repo_corpus_enabled=%s",
        settings.crawl_inbox_path,
        settings.material_merge_extra_roots,
        settings.organized_batch_id,
        settings.poll_interval_seconds,
        settings.run_once,
        settings.dry_run,
        settings.organize_loop_idle_cycles_before_exit,
        settings.analyzed_output_path,
        settings.analyzed_output_enabled,
        settings.repository_corpus_enabled,
    )

    cycles = 0
    idle_count = 0
    last_cycle_row_count: int | None = None
    last_cycle_failed = False
    while not stop.is_set():
        cycles += 1
        rows: list[dict[str, Any]] = []
        cycle_err: str | None = None
        try:
            rows = collect_cycle(settings)
            logger.info(
                "organize-loop ciclo OK — %s documentos normalizados; próximo ciclo em %ss",
                len(rows),
                settings.poll_interval_seconds,
            )
        except Exception:
            logger.exception("Falha no ciclo de organização; retento após o intervalo")
            cycle_err = "exceção no ciclo organize-loop (ver logs)"
        refresh_organize_preview_after_cycle(
            settings,
            loop_name="organize-loop",
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
        threshold = settings.organize_loop_idle_cycles_before_exit
        if threshold > 0 and cycle_err is None and idle_count >= threshold:
            logger.info(
                "organize-loop: %s ciclos seguidos sem novos documentos — encerrando (fila vazia).",
                threshold,
            )
            break
        if settings.run_once:
            logger.info("organize-loop run_once — encerrando após um ciclo.")
            break
        if stop.wait(timeout=float(settings.poll_interval_seconds)):
            break

    logger.info("organize-loop encerrado (%s ciclos)", cycles)
    emit_local_loop_finished_banner("organize-loop", settings, cycles=cycles)
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
