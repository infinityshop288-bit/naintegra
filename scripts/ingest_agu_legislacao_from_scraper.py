#!/usr/bin/env python3
"""Ingere legislação AGU coletada pelo naintegracursos-scraper → public.norma_chunks (Lex).

Lê JSONL em data/processed/legislacao_agu/ (scraper) ou data/legislacao_agu/ (cópia local).

Uso:
  set -a && source .env && set +a
  python3 scripts/ingest_agu_legislacao_from_scraper.py
  python3 scripts/ingest_agu_legislacao_from_scraper.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from naintegra_lex_agent.legal_text import pick_display_title, pick_verbatim_body  # noqa: E402
from naintegra_lex_agent.norma_chunks import (  # noqa: E402
    fix_text_encoding,
    legis_meta_from_url,
    list_catalog_doc_keys,
    normalize_norma_url,
    refresh_catalog_mv,
    rows_from_document,
    upsert_rows_rpc,
)

SOURCE = "planalto"
MIN_TEXT_LEN = 200
DEFAULT_SCRAPER = Path("/Users/luizcarlos/naintegracursos-scraper/data/processed/legislacao_agu")


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def load_agu_records(input_dir: Path) -> list[dict]:
    files = sorted(input_dir.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"Nenhum JSONL em {input_dir}")
    by_url: dict[str, dict] = {}
    for fp in files:
        for rec in _iter_jsonl(fp):
            url = str(rec.get("url") or "").strip()
            if not url:
                continue
            key = normalize_norma_url(url)
            body = pick_verbatim_body(rec) or ""
            prev = by_url.get(key)
            if not prev or len(body) > len(pick_verbatim_body(prev) or ""):
                by_url[key] = rec
    return list(by_url.values())


def _carreira_tags(tags: list) -> list[str]:
    out: list[str] = []
    for t in tags or []:
        if not isinstance(t, str):
            continue
        if t.startswith("agu:"):
            continue
        if t in ("planalto", "agu"):
            continue
        if "_2022" in t or t in ("pgfn", "advogado", "procurador_federal", "bacen"):
            out.append(t)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingere legislação AGU → norma_chunks")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(os.environ.get("AGU_LEGIS_INPUT_DIR", str(DEFAULT_SCRAPER))),
        help="Pasta com legislacao_agu_*.jsonl",
    )
    parser.add_argument("--force", action="store_true", help="Reingere mesmo se já no catálogo")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    records = load_agu_records(input_dir)
    print(f"[INFO] {len(records)} norma(s) AGU em {input_dir}")

    sb_url = os.environ.get("LEX_AGENT_SUPABASE_URL", "").strip()
    key = os.environ.get("LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not args.dry_run and (not sb_url or not key):
        print("[ERRO] Defina LEX_AGENT_SUPABASE_URL e LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY.", file=sys.stderr)
        return 1

    have: set[str] = set()
    if not args.dry_run:
        have = list_catalog_doc_keys(supabase_url=sb_url, supabase_key=key, source=SOURCE)

    total_rows = 0
    published = 0
    skipped = 0

    for rec in records:
        url = normalize_norma_url(str(rec.get("url") or ""))
        if not url.startswith("https://"):
            print(f"[SKIP] URL inválida: {rec.get('title')}")
            skipped += 1
            continue
        doc_key = url
        if doc_key in have and not args.force:
            skipped += 1
            continue

        body = fix_text_encoding((pick_verbatim_body(rec) or "").strip())
        if len(body) < MIN_TEXT_LEN:
            print(f"[WARN] texto curto ({len(body)}): {rec.get('title')}", file=sys.stderr)
            skipped += 1
            continue

        titulo = pick_display_title(rec) or str(rec.get("title") or "").strip()
        meta_url = legis_meta_from_url(url)
        secao = meta_url.get("secao_lei_seca") or "Legislação Especial"
        if titulo and meta_url.get("titulo"):
            titulo = meta_url["titulo"]
        tags = rec.get("tags") or []
        extra = {
            "corpus": "legislacao_agu",
            "collection": rec.get("collection") or "legislacao_agu",
            "carreiras_agu": _carreira_tags(tags),
            "agu_slugs": [t.split(":", 1)[1] for t in tags if isinstance(t, str) and t.startswith("agu:")],
            "legal_act_type": rec.get("legal_act_type"),
        }

        rows = rows_from_document(
            source=SOURCE,
            url=url,
            body=body,
            titulo=titulo or None,
            secao_lei_seca=secao,
            source_file=f"legislacao_agu/{doc_key.split('/')[-1] or 'norma'}.jsonl",
            extra_metadata=extra,
        )
        if args.dry_run:
            print(f"[dry-run] {titulo} → {len(rows)} chunk(s)")
            published += 1
            total_rows += len(rows)
            continue

        n = upsert_rows_rpc(rows, supabase_url=sb_url, supabase_key=key)
        total_rows += n
        published += 1
        print(f"[OK] {n} chunk(s) → {titulo}")

    if total_rows and not args.dry_run:
        refresh_catalog_mv(supabase_url=sb_url, supabase_key=key)

    print(f"\nConcluído: {published} doc(s), {total_rows} chunk(s), {skipped} ignorado(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
