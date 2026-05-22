"""Loop contínuo: consolida legislação/jurisprudência → public.norma_chunks (Lex).

A cada ciclo:
  1. Funde JSONL/markdown coletados (Trilhante, Rideel, inbox, pastas extras)
  2. Normaliza e formata (Ollama opcional para limpar crawl)
  3. Upsert em norma_chunks + refresh do catálogo

Variáveis principais (prefixo LEX_AGENT_):
  NORMA_MARKDOWN_ROOTS — pastas .md adicionais (vírgula)
  NORMA_AI_FORMAT_ENABLED=true — formatação via Ollama
  NORMA_AI_FORMAT_MODE=fallback|always|off
  AI_PROVIDER=ollama — classificação/enriquecimento opcional
  SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY — destino Lex

Um ciclo: LEX_AGENT_RUN_ONCE=true naintegra-norma-consolidate-loop
"""

from __future__ import annotations

import logging
import signal
import sys
import threading

from .agent import _configure_logging
from .material_merge import settings_with_trilhante_informativo_root
from .norma_consolidate import consolidate_cycle
from .organize_loop import apply_organize_merge_roots
from .settings import Settings, load_settings
from .state_store import StateStore

logger = logging.getLogger("naintegra_lex_agent.norma_consolidate_loop")


def apply_norma_consolidate_defaults(settings: Settings) -> Settings:
    updates: dict[str, object] = {"material_merge_before_cycle": True}
    if settings.norma_ai_format_enabled and settings.ai_provider == "anthropic":
        updates["ai_provider"] = "ollama"
    return settings.model_copy(update=updates)


def main_sync() -> None:
    settings = apply_norma_consolidate_defaults(
        settings_with_trilhante_informativo_root(
            apply_organize_merge_roots(load_settings())
        )
    )
    _configure_logging(settings.log_level)

    stop = threading.Event()

    def _stop(*_: object) -> None:
        logger.info("Encerrando norma-consolidate-loop (sinal)...")
        stop.set()

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    state = StateStore(settings.norma_consolidate_state_db_path)
    logger.info(
        "NaIntegra norma-consolidate-loop — intervalo=%ss run_once=%s dry_run=%s "
        "markdown_roots=%s ai_format=%s mode=%s supabase=%s",
        settings.poll_interval_seconds,
        settings.run_once,
        settings.dry_run,
        settings.norma_markdown_roots or "(trilhante + merge roots)",
        settings.norma_ai_format_enabled,
        settings.norma_ai_format_mode,
        settings.has_supabase_credentials(),
    )

    cycles = 0
    idle = 0
    try:
        while not stop.is_set():
            cycles += 1
            try:
                result = consolidate_cycle(settings, state)
                st = result.stats
                logger.info(
                    "norma-consolidate ciclo %s — scan=%s norm=%s pub_docs=%s chunks=%s "
                    "skip=%s unpublishable=%s ai_fmt=%s err=%s",
                    cycles,
                    st.scanned,
                    st.normalized,
                    st.published_docs,
                    st.published_chunks,
                    st.skipped_state,
                    st.skipped_unpublishable,
                    st.ai_formatted,
                    st.errors,
                )
                if st.published_docs == 0 and st.scanned == 0:
                    idle += 1
                elif st.published_docs == 0 and st.skipped_state >= st.scanned and st.scanned > 0:
                    idle += 1
                else:
                    idle = 0
            except Exception:
                logger.exception("Falha no ciclo norma-consolidate")
                idle = 0

            threshold = settings.norma_consolidate_loop_idle_cycles_before_exit
            if threshold > 0 and idle >= threshold:
                logger.info(
                    "norma-consolidate: %s ciclos ociosos — encerrando (material consolidado).",
                    threshold,
                )
                break
            if settings.run_once:
                break
            if stop.wait(timeout=float(settings.poll_interval_seconds)):
                break
    finally:
        state.close()

    logger.info("norma-consolidate-loop encerrado (%s ciclos)", cycles)
    sys.exit(0)


def main() -> None:
    main_sync()


if __name__ == "__main__":
    main_sync()
