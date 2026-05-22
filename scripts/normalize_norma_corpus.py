#!/usr/bin/env python3
"""Normaliza corpus em norma_chunks (URLs, metadata de catálogo, refresh MV).

Uso:
  set -a && source .env && set +a
  python3 scripts/normalize_norma_corpus.py
  python3 scripts/normalize_norma_corpus.py --source planalto --reupsert-text
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from naintegra_lex_agent.norma_chunks import refresh_catalog_mv, upsert_rows_rpc  # noqa: E402


def _headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def rpc(supabase_url: str, key: str, name: str, body: dict | None = None) -> Any:
    with httpx.Client(timeout=600) as client:
        r = client.post(
            f"{supabase_url.rstrip('/')}/rest/v1/rpc/{name}",
            headers=_headers(key),
            json=body or {},
        )
        r.raise_for_status()
        return r.json()


def fetch_chunks(supabase_url: str, key: str, source: str | None) -> list[dict]:
    headers = _headers(key)
    out: list[dict] = []
    offset = 0
    page_size = 1000
    base = supabase_url.rstrip("/")
    with httpx.Client(timeout=120) as client:
        while True:
            q = (
                "select=id,source,source_file,url,chunk_index,text,metadata"
                f"&order=source.asc,url.asc,chunk_index.asc"
                f"&limit={page_size}&offset={offset}"
            )
            if source:
                q += f"&source=eq.{source}"
            r = client.get(f"{base}/rest/v1/norma_chunks?{q}", headers=headers)
            r.raise_for_status()
            rows = r.json()
            if not rows:
                break
            out.extend(rows)
            if len(rows) < page_size:
                break
            offset += page_size
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Normaliza norma_chunks no Supabase")
    parser.add_argument("--source", help="Fonte específica")
    parser.add_argument("--refresh-only", action="store_true")
    parser.add_argument(
        "--reupsert-text",
        action="store_true",
        help="Re-upsert completo (corrige encoding); use com --source planalto",
    )
    args = parser.parse_args()

    url = os.environ.get("LEX_AGENT_SUPABASE_URL", "").strip()
    key = os.environ.get("LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        print("Defina LEX_AGENT_SUPABASE_URL e LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        return 1

    if args.refresh_only:
        ok = refresh_catalog_mv(supabase_url=url, supabase_key=key)
        print("[OK] MV refrescada" if ok else "[WARN] refresh expirou; rode enrich_norma_catalog_chunks no SQL")
        return 0

    try:
        stats = rpc(url, key, "normalize_norma_chunks_corpus")
        print(f"[OK] normalize_norma_chunks_corpus: {stats}")
    except httpx.HTTPStatusError as exc:
        print(f"[WARN] normalize_norma_chunks_corpus: {exc.response.text[:200]}", file=sys.stderr)

    try:
        body = {"p_source": args.source} if args.source else {"p_source": None}
        n = rpc(url, key, "enrich_norma_catalog_chunks", body)
        print(f"[OK] enrich_norma_catalog_chunks: {n} chunk(s) de catálogo")
    except httpx.HTTPStatusError as exc:
        print(f"[WARN] enrich_norma_catalog_chunks: {exc.response.text[:200]}", file=sys.stderr)

    if args.reupsert_text:
        rows = fetch_chunks(url, key, args.source)
        print(f"[INFO] re-upsert de {len(rows)} chunk(s)")
        total = upsert_rows_rpc(rows, supabase_url=url, supabase_key=key)
        refresh_catalog_mv(supabase_url=url, supabase_key=key)
        print(f"[OK] {total} chunk(s) re-upsert(s)")
    else:
        refresh_catalog_mv(supabase_url=url, supabase_key=key)
        print("[OK] catálogo refrescado")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
