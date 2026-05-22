"""Publicação Lex → Supabase (`lex.ingested_documents`), consumido pelo app NaIntegra Cursos."""

from __future__ import annotations

import logging
import sys
from typing import Any

from .agent import collect_cycle, _configure_logging
from .material_merge import settings_with_trilhante_informativo_root
from .settings import Settings, load_settings
from .state_store import StateStore
from .supabase_sink import upsert_batches

logger = logging.getLogger(__name__)


def publish_lex_rows(settings: Settings, rows: list[dict[str, Any]]) -> int:
    """Upsert no Supabase; retorna quantos registros efetivamente enviados (após dedupe de estado, se aplicável)."""

    if not rows:
        return 0

    if settings.publish_ignore_state:
        uploaded = upsert_batches(rows, settings)
        if uploaded and not settings.dry_run:
            store = StateStore(settings.state_db_path)
            try:
                for row in rows:
                    store.mark(row["external_id"], row.get("content_hash") or "")
            finally:
                store.close()
        return len(rows) if uploaded else 0

    store = StateStore(settings.state_db_path)
    try:
        pending: list[dict[str, Any]] = []
        for row in rows:
            eid = row["external_id"]
            ch = row.get("content_hash") or ""
            if store.should_skip(eid, ch):
                continue
            pending.append(row)
        if pending:
            uploaded = upsert_batches(pending, settings)
            if uploaded and not settings.dry_run:
                for row in pending:
                    store.mark(row["external_id"], row.get("content_hash") or "")
            return len(pending) if uploaded else 0
        return 0
    finally:
        store.close()


def run_trilhante_publish_once(settings: Settings) -> tuple[int, int]:
    """Fusão (incl. Trilhante) → normalize → categorização → upsert Supabase (site NaIntegra Cursos)."""

    s = settings_with_trilhante_informativo_root(settings)
    s = s.model_copy(update={"material_merge_before_cycle": True})
    rows_list = collect_cycle(s)
    published = publish_lex_rows(s, rows_list)
    logger.info(
        "Trilhante → NaIntegra: %s documentos normalizados; %s enviados ao Supabase (%s.%s) nesta rodada",
        len(rows_list),
        published,
        s.lex_schema,
        s.lex_table,
    )
    return len(rows_list), published


def main_sync(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Funde JSONL de LEX_AGENT_TRILHANTE_INFORMATIVO_ROOT (e demais roots), normaliza/categoriza "
            "e faz upsert em lex.ingested_documents (backend do NaIntegra Cursos / naintegracursos.com.br)."
        )
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="Ignora dedupe em .lex_agent/state.sqlite e tenta upsert de todos os registros do ciclo.",
    )
    args = parser.parse_args(argv)

    settings = load_settings()
    if args.force_all:
        settings = settings.model_copy(update={"publish_ignore_state": True})

    _configure_logging(settings.log_level)
    run_trilhante_publish_once(settings)


def main() -> None:
    main_sync(None)
    sys.exit(0)


if __name__ == "__main__":
    main()
