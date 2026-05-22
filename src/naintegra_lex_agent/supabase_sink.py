from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .settings import Settings

logger = logging.getLogger(__name__)


def upsert_batches(rows: list[dict[str, Any]], settings: Settings) -> bool:
    """Envia linhas ao Supabase.

    Retorna ``True`` em dry-run ou após upsert bem-sucedido. Retorna ``False`` quando não há credenciais
    (sem levantar erro — conteúdo permanece só em disco pelo ``collect_cycle``).
    """

    if not rows:
        return False
    if settings.dry_run:
        logger.info("[dry-run] Enviaria %s linhas ao Supabase (%s.%s)", len(rows), settings.lex_schema, settings.lex_table)
        return True
    if not settings.has_supabase_credentials():
        logger.warning(
            "Supabase não configurado — upsert ignorado (%s documentos só em manifest/corpus local)",
            len(rows),
        )
        return False

    try:
        from supabase import create_client
    except ImportError as e:
        raise RuntimeError(
            "Dependência 'supabase' não instalada. Use: pip install 'naintegra-lex-agent[supabase]'"
        ) from e

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    sb_table = client.schema(settings.lex_schema).table(settings.lex_table)

    batch_size = max(1, settings.batch_size)
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        sb_table.upsert(chunk, on_conflict="external_id").execute()

    logger.info("Supabase: upsert de %s documentos em %s.%s", len(rows), settings.lex_schema, settings.lex_table)
    return True
