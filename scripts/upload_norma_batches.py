#!/usr/bin/env python3
"""Envia batches JSON (.tmp_norma_ingest/batch_*.json) para norma_chunks via RPC padronizado."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from naintegra_lex_agent.norma_chunks import refresh_catalog_mv, upsert_rows_rpc  # noqa: E402


def main() -> int:
    url = os.environ.get("LEX_AGENT_SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        print("Defina LEX_AGENT_SUPABASE_URL e LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        return 1

    ingest_dir = Path(os.environ.get("NORMA_INGEST_DIR", ".tmp_norma_ingest"))
    pattern = os.environ.get("NORMA_INGEST_GLOB", "batch_*.json")
    files = sorted(ingest_dir.glob(pattern))
    if not files:
        print(f"Nenhum arquivo em {ingest_dir}/{pattern}", file=sys.stderr)
        return 2

    total = 0
    for path in files:
        rows = json.loads(path.read_text(encoding="utf-8"))
        n = upsert_rows_rpc(rows, supabase_url=url, supabase_key=key)
        total += n
        print(f"[OK] {path.name}: {n} row(s)")

    refresh_catalog_mv(supabase_url=url, supabase_key=key)
    print(f"Total upserted: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
