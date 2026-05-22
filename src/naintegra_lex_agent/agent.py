from __future__ import annotations

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ai_cache import AIDecisionCache
from .ingest import iter_inbox_files, iter_records_from_file
from .material_merge import merge_material_into_corpus, settings_with_trilhante_informativo_root
from .organized_output import write_organized_manifest
from .pipeline import select_and_normalize
from .preservation import copy_inbox_files_to_preservation
from .settings import Settings, load_settings
from .state_store import StateStore
from .supabase_sink import upsert_batches

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def collect_cycle(settings: Settings) -> list[dict[str, Any]]:
    if settings.material_merge_before_cycle:
        merge_material_into_corpus(settings)

    files = iter_inbox_files(settings.crawl_inbox_path, settings.crawl_glob, settings.also_scan_json)
    batch_token = (settings.organized_batch_id or "").strip()
    batch_id = batch_token if batch_token else datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    preserved_map: dict[Path, str] = {}
    if settings.preserve_inbox_files and files:
        settings.raw_preserved_path.mkdir(parents=True, exist_ok=True)
        preserved_map = copy_inbox_files_to_preservation(files, settings.raw_preserved_path, batch_id)

    inbox_root = settings.crawl_inbox_path.resolve()

    raw: list[dict[str, Any]] = []
    for path in files:
        resolved = path.resolve()
        pres_rel = preserved_map.get(resolved) if settings.preserve_inbox_files else None
        try:
            inbox_rel = str(path.relative_to(inbox_root))
        except ValueError:
            inbox_rel = path.name

        for rec in iter_records_from_file(path):
            rec["_preservation_batch"] = batch_id
            rec["_inbox_file_relpath"] = inbox_rel
            if pres_rel:
                rec["_preservation_file_relpath"] = pres_rel
            raw.append(rec)
            if len(raw) >= settings.max_records_per_cycle:
                break
        if len(raw) >= settings.max_records_per_cycle:
            break

    ai_cache: AIDecisionCache | None = None
    if settings.ai_enabled:
        ai_cache = AIDecisionCache(settings.ai_cache_path)
    try:
        normalized = select_and_normalize(raw, settings, ai_cache)
    finally:
        if ai_cache is not None:
            ai_cache.close()

    if settings.write_organized_manifest:
        settings.organized_output_path.mkdir(parents=True, exist_ok=True)
        write_organized_manifest(settings.organized_output_path, batch_id, normalized)

    if settings.analyzed_output_enabled and normalized:
        if settings.dry_run:
            logger.info(
                "[dry-run] Pasta analisada/categorizada: ignoraria batch=%s → %s",
                batch_id,
                settings.analyzed_output_path,
            )
        else:
            settings.analyzed_output_path.mkdir(parents=True, exist_ok=True)
            write_organized_manifest(
                settings.analyzed_output_path,
                batch_id,
                normalized,
                kind="analisado/categorizado",
            )

    if settings.sync_preview_manifest and normalized:
        import shutil

        man = settings.organized_output_path / batch_id / "manifest.jsonl"
        dest = settings.preview_manifest_path
        if man.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(man, dest)

    rows: list[dict[str, Any]] = []
    for doc in normalized:
        rows.append(doc.row_for_supabase())

    if settings.repository_corpus_enabled and rows:
        if settings.dry_run:
            logger.info(
                "[dry-run] Corpus do repositório: ignoraria %s linhas → %s",
                len(rows),
                settings.repository_corpus_path,
            )
        else:
            from .repository_corpus import merge_rows_into_repository_corpus

            merge_rows_into_repository_corpus(settings.repository_corpus_path, rows)

    return rows


async def process_single_cycle(settings: Settings, store: StateStore) -> int:
    pending_rows: list[dict[str, Any]] = []
    for row in collect_cycle(settings):
        eid = row["external_id"]
        ch = row.get("content_hash") or ""
        if store.should_skip(eid, ch):
            continue
        pending_rows.append(row)

    if pending_rows:
        uploaded = await asyncio.to_thread(upsert_batches, pending_rows, settings)
        if uploaded:
            for row in pending_rows:
                store.mark(row["external_id"], row.get("content_hash") or "")
            logger.info("Ciclo OK: %s documentos novos/atualizados (Supabase ou dry-run)", len(pending_rows))
        else:
            logger.info(
                "Ciclo OK: %s documentos processados em disco; upsert Supabase pendente (credenciais ausentes)",
                len(pending_rows),
            )
    else:
        logger.debug("Ciclo sem novidades")
    return len(pending_rows)


async def run_loop(settings: Settings, stop_event: asyncio.Event) -> None:
    store = StateStore(settings.state_db_path)
    try:
        while not stop_event.is_set():
            try:
                await process_single_cycle(settings, store)
            except Exception:
                logger.exception("Falha no ciclo do agente; próxima tentativa após intervalo")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=settings.poll_interval_seconds)
            except TimeoutError:
                pass
    finally:
        store.close()


async def run_once(settings: Settings) -> None:
    store = StateStore(settings.state_db_path)
    try:
        await process_single_cycle(settings, store)
    finally:
        store.close()


def main_sync() -> None:
    settings = settings_with_trilhante_informativo_root(load_settings())
    _configure_logging(settings.log_level)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop_event = asyncio.Event()

    def _handle_signal(*_: Any) -> None:
        logger.info("Encerrando agente (sinal recebido)...")
        stop_event.set()

    signums: list[int] = [signal.SIGINT]
    if hasattr(signal, "SIGTERM"):
        signums.append(signal.SIGTERM)

    for sig in signums:
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:

            def _sync_handler(_sig: int, _frame: Any) -> None:
                stop_event.set()

            signal.signal(sig, _sync_handler)

    logger.info(
        "NaIntegra Lex Agent — inbox=%s intervalo=%ss dry_run=%s run_once=%s ai=%s/%s "
        "analisado_output=%s",
        settings.crawl_inbox_path,
        settings.poll_interval_seconds,
        settings.dry_run,
        settings.run_once,
        settings.ai_enabled,
        settings.ai_mode,
        settings.analyzed_output_enabled,
    )
    try:
        if settings.run_once:
            loop.run_until_complete(run_once(settings))
        else:
            loop.run_until_complete(run_loop(settings, stop_event))
    finally:
        loop.close()


def main() -> None:
    main_sync()


if __name__ == "__main__":
    main_sync()
