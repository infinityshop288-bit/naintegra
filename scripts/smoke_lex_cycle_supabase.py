#!/usr/bin/env python3
"""Smoke: um ``collect_cycle`` mínimo + upsert opcional no Supabase; remove o registro ``__smoke_*`` ao final.

Uso (na raiz do repo, com .env preenchido):
  PYTHONPATH=src python3 scripts/smoke_lex_cycle_supabase.py

Sem ``LEX_AGENT_SUPABASE_*``: apenas valida normalização e encerra com SKIP Supabase.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from naintegra_lex_agent.agent import collect_cycle  # noqa: E402
    from naintegra_lex_agent.lex_publish import publish_lex_rows  # noqa: E402
    from naintegra_lex_agent.settings import load_settings  # noqa: E402

    inbox = repo_root / ".tmp_smoke_lex_inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    eid = f"__smoke_naintegra_lex_{int(time.time())}"
    (inbox / "smoke.jsonl").write_text(
        json.dumps(
            {
                "id": eid,
                "type": "legislacao",
                "titulo": "Smoke test NaIntegra Lex",
                "texto": "Artigo único. Registro temporário de teste automatizado.",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    base = load_settings()
    settings = base.model_copy(
        update={
            "crawl_inbox_path": inbox,
            "material_merge_before_cycle": False,
            "preserve_inbox_files": False,
            "write_organized_manifest": False,
            "dry_run": False,
            "repository_corpus_enabled": False,
            "analyzed_output_enabled": False,
            "sync_preview_manifest": False,
            "ai_enabled": False,
            "max_records_per_cycle": 10,
        }
    )

    rows = collect_cycle(settings)
    print(f"[OK] collect_cycle: {len(rows)} documento(s) normalizado(s)")
    if not rows:
        print("[FAIL] Nenhuma linha normalizada (pipeline)")
        return 2

    if not settings.supabase_url or not settings.supabase_service_role_key:
        print(
            "[SKIP] Supabase: defina LEX_AGENT_SUPABASE_URL e LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY no .env "
            "para testar upsert real."
        )
        return 0

    pub_settings = settings.model_copy(update={"publish_ignore_state": True})
    n_sent = publish_lex_rows(pub_settings, rows)
    print(f"[OK] publish_lex_rows: {n_sent} linha(s) enviada(s) a {settings.lex_schema}.{settings.lex_table}")

    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        tbl = client.schema(settings.lex_schema).table(settings.lex_table)
        tbl.delete().eq("external_id", eid).execute()
        print(f"[OK] Limpeza Supabase: removido external_id={eid}")
    except Exception as exc:
        print(f"[WARN] Falha ao remover smoke no Supabase ({exc}). Remova manualmente: external_id={eid}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
