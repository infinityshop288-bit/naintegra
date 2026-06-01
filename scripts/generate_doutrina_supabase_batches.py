#!/usr/bin/env python3
"""Gera SQL de upsert em lotes para lex.ingested_documents (uso com Supabase SQL / MCP)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SRC = REPO / "repository" / "lex_corpus.jsonl"


def pg_text(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def pg_jsonb(value: object) -> str:
    payload = json.dumps(value or {}, ensure_ascii=False).replace("'", "''")
    return f"'{payload}'::jsonb"


def load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def batch_sql(rows: list[dict]) -> str:
    parts: list[str] = []
    for r in rows:
        parts.append(
            "("
            + ", ".join(
                [
                    pg_text(r["external_id"]),
                    pg_text(r["doc_type"]),
                    pg_text(r.get("source_system")),
                    pg_text(r.get("title")),
                    pg_text(r.get("body")),
                    pg_jsonb(r.get("meta")),
                    pg_jsonb(r.get("organized")),
                    pg_text(r.get("crawl_batch_id")),
                    pg_text(r.get("content_hash")),
                ]
            )
            + ")"
        )
    return (
        "INSERT INTO lex.ingested_documents "
        "(external_id, doc_type, source_system, title, body, meta, organized, crawl_batch_id, content_hash)\n"
        f"VALUES\n  {',\n  '.join(parts)}\n"
        "ON CONFLICT (external_id) DO UPDATE SET\n"
        "  doc_type = EXCLUDED.doc_type,\n"
        "  source_system = EXCLUDED.source_system,\n"
        "  title = EXCLUDED.title,\n"
        "  body = EXCLUDED.body,\n"
        "  meta = EXCLUDED.meta,\n"
        "  organized = EXCLUDED.organized,\n"
        "  crawl_batch_id = EXCLUDED.crawl_batch_id,\n"
        "  content_hash = EXCLUDED.content_hash,\n"
        "  updated_at = now();"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--src", type=Path, default=DEFAULT_SRC)
    p.add_argument("--batch-size", type=int, default=250)
    p.add_argument("--batch-index", type=int, default=None)
    p.add_argument("--out-dir", type=Path, default=REPO / "data" / "cp_iuris_2025" / "supabase_batches")
    p.add_argument("--write-all", action="store_true", help="Grava todos os lotes em out-dir")
    args = p.parse_args()

    rows = load_rows(args.src.expanduser().resolve())
    if args.write_all:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        n_batches = (len(rows) + args.batch_size - 1) // args.batch_size
        for i in range(n_batches):
            chunk = rows[i * args.batch_size : (i + 1) * args.batch_size]
            out = args.out_dir / f"batch_{i:04d}.sql"
            out.write_text(batch_sql(chunk), encoding="utf-8")
        print(f"{n_batches} lote(s) → {args.out_dir}")
        return 0

    if args.batch_index is None:
        p.error("--batch-index é obrigatório sem --write-all")

    chunk = rows[args.batch_index * args.batch_size : (args.batch_index + 1) * args.batch_size]
    if not chunk:
        return 0
    print(batch_sql(chunk))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
