#!/usr/bin/env python3
"""Ingere legislação do Planalto em public.norma_chunks (formato padronizado Lex).

Prefira o job semanal:
  python3 scripts/update_lex_legislacao_semanal.py

Uso pontual (primeira carga):
  set -a && source .env && set +a
  python3 scripts/ingest_planalto_to_norma_chunks.py [--force]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from naintegra_lex_agent.norma_chunks import (  # noqa: E402
    list_catalog_doc_keys,
    normalize_norma_url,
    refresh_catalog_mv,
    rows_from_document,
    supabase_headers,
    upsert_rows_rpc,
)
from naintegra_lex_agent.planalto_legis import (  # noqa: E402
    PLANALTO_LEGIS_CATALOG,
    fetch_planalto_text,
)

SOURCE = "planalto"


def delete_document_chunks(sb_url: str, key: str, law_url: str) -> int:
    doc_url = normalize_norma_url(law_url)
    urls = {doc_url, doc_url.replace("https://", "http://"), law_url.strip()}
    headers = {**supabase_headers(key), "Prefer": "return=representation"}
    deleted = 0
    with httpx.Client(timeout=180) as client:
        for u in urls:
            if not u:
                continue
            r = client.delete(
                f"{sb_url.rstrip('/')}/rest/v1/norma_chunks?source=eq.planalto&url=eq.{quote(u, safe='')}",
                headers=headers,
            )
            if r.status_code >= 400:
                continue
            if r.text:
                try:
                    deleted += len(r.json())
                except Exception:
                    pass
    return deleted


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Ingere legislação Planalto → norma_chunks")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-baixa e sobrescreve mesmo se já estiver no catálogo",
    )
    args = parser.parse_args()

    sb_url = os.environ.get("LEX_AGENT_SUPABASE_URL", "").strip()
    key = os.environ.get("LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not sb_url or not key:
        print(
            "[SKIP] Defina LEX_AGENT_SUPABASE_URL e LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY.",
            file=sys.stderr,
        )
        return 1

    have = list_catalog_doc_keys(supabase_url=sb_url, supabase_key=key, source=SOURCE)
    total_rows = 0

    for law in PLANALTO_LEGIS_CATALOG:
        doc_key = normalize_norma_url(law["url"])
        if doc_key in have and not args.force:
            print(f"[SKIP] já no catálogo: {law['titulo']}")
            continue
        if args.force and doc_key in have:
            n_del = delete_document_chunks(sb_url, key, law["url"])
            print(f"[DEL] {n_del} chunk(s) antigos → {law['titulo']}")
        print(f"[FETCH] {law['titulo']} …")
        try:
            fetched = fetch_planalto_text(law["url"])
            text = fetched.text
        except Exception as exc:
            print(f"[WARN] falha ao baixar {law['url']}: {exc}", file=sys.stderr)
            continue
        if len(text) < 200:
            print(f"[WARN] texto curto demais ({len(text)} chars): {law['url']}", file=sys.stderr)
            continue
        rows = rows_from_document(
            source=SOURCE,
            url=law["url"],
            body=text,
            titulo=law["titulo"],
            secao_lei_seca=law["secao"],
            extra_metadata={
                "corpus": "legislacao_planalto_ingest",
                "content_hash": fetched.content_hash,
            },
        )
        n = upsert_rows_rpc(rows, supabase_url=sb_url, supabase_key=key)
        total_rows += n
        print(f"[OK] {n} chunk(s) → {law['titulo']}")

    if total_rows:
        refresh_catalog_mv(supabase_url=sb_url, supabase_key=key)
    print(f"\nConcluído: {total_rows} chunk(s) enviados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
