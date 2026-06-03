#!/usr/bin/env python3
"""Normaliza corpus em norma_chunks (URLs, metadata, português jurídico, refresh MV).

Uso:
  set -a && source .env && set +a
  python3 scripts/normalize_norma_corpus.py
  python3 scripts/normalize_norma_corpus.py --apply-portuguese --only-stale
  python3 scripts/normalize_norma_corpus.py --source planalto --apply-portuguese
  python3 scripts/normalize_norma_corpus.py --source trilhante_informativo --apply-portuguese --dry-run
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

from naintegra_lex_agent.norma_chunks import (  # noqa: E402
    refresh_catalog_mv,
    reapply_pt_norma_rows,
    upsert_rows_rpc,
)
from naintegra_lex_agent.pt_norma import VERSION as PT_NORMA_VERSION  # noqa: E402


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


def apply_portuguese_corpus(
    *,
    supabase_url: str,
    key: str,
    source: str | None,
    only_stale: bool,
    dry_run: bool,
) -> int:
    rows = fetch_chunks(supabase_url, key, source)
    print(f"[INFO] {len(rows)} chunk(s) carregados (pt_norma v{PT_NORMA_VERSION})")
    to_upsert, changed, skipped = reapply_pt_norma_rows(rows, only_stale=only_stale)
    print(
        f"[INFO] alterados: {changed} | ignorados (já em v{PT_NORMA_VERSION}): {skipped} | "
        f"sem mudança de texto: {len(rows) - changed - skipped}"
    )
    if dry_run:
        print("[DRY-RUN] Nenhum upsert executado.")
        return 0
    if not to_upsert:
        print("[OK] Nenhum chunk precisou de atualização.")
        refresh_catalog_mv(supabase_url=supabase_url, supabase_key=key)
        return 0
    total = upsert_rows_rpc(to_upsert, supabase_url=supabase_url, supabase_key=key)
    refresh_catalog_mv(supabase_url=supabase_url, supabase_key=key)
    print(f"[OK] {total} chunk(s) gravados no Supabase com português normalizado.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Normaliza norma_chunks no Supabase")
    parser.add_argument("--source", help="Fonte: planalto, trilhante_informativo, rideel_vademecum, …")
    parser.add_argument("--refresh-only", action="store_true")
    parser.add_argument(
        "--apply-portuguese",
        action="store_true",
        help=(
            "Reaplica pt_norma (ortografia, tipografia, citações) e persiste texto em norma_chunks "
            f"(versão atual: {PT_NORMA_VERSION})"
        ),
    )
    parser.add_argument(
        "--only-stale",
        action="store_true",
        help="Com --apply-portuguese: só chunks com metadata.pt_norma_version diferente da atual",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Com --apply-portuguese: mostra quantos chunks mudariam, sem gravar",
    )
    parser.add_argument(
        "--reupsert-text",
        action="store_true",
        help="Alias de --apply-portuguese (retrocompat.)",
    )
    args = parser.parse_args()

    url = os.environ.get("LEX_AGENT_SUPABASE_URL", "").strip()
    key = os.environ.get("LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        print("Defina LEX_AGENT_SUPABASE_URL e LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        return 1

    apply_pt = args.apply_portuguese or args.reupsert_text

    if args.refresh_only:
        ok = refresh_catalog_mv(supabase_url=url, supabase_key=key)
        print("[OK] MV refrescada" if ok else "[WARN] refresh expirou; rode enrich_norma_catalog_chunks no SQL")
        return 0

    if apply_pt:
        return apply_portuguese_corpus(
            supabase_url=url,
            key=key,
            source=args.source,
            only_stale=args.only_stale,
            dry_run=args.dry_run,
        )

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

    refresh_catalog_mv(supabase_url=url, supabase_key=key)
    print("[OK] catálogo refrescado")
    print(
        f"[DICA] Para persistir português jurídico no banco: "
        f"python3 scripts/normalize_norma_corpus.py --apply-portuguese --only-stale"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
