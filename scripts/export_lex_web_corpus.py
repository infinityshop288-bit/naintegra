#!/usr/bin/env python3
"""Exporta corpus Lex (repositório / manifest / inbox) para JSON consumido pelo front em web/lex/."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(f"[warn] {path}:{lineno} JSON inválido ({exc})", file=sys.stderr)
    return rows


def _normalize_inbox_row(row: dict[str, Any]) -> dict[str, Any]:
    eid = str(row.get("external_id") or row.get("id") or "").strip()
    doc_type = row.get("doc_type") or row.get("type") or "legislacao"
    meta = dict(row.get("meta") or row.get("metadata") or {})
    organized = dict(row.get("organized") or {})
    body = row.get("body") or row.get("dispositivo") or row.get("dispositivo_legal") or row.get("texto")
    if row.get("enunciado") and not body:
        body = row["enunciado"]
    if meta.get("ementa") and doc_type in ("jurisprudencia", "sumula") and not body:
        body = meta["ementa"]
    return {
        "external_id": eid,
        "doc_type": doc_type,
        "source_system": row.get("source_system") or row.get("source"),
        "title": row.get("title") or row.get("titulo"),
        "body": body,
        "meta": meta,
        "organized": organized,
    }


def _normalize_manifest_row(row: dict[str, Any]) -> dict[str, Any]:
    org = row.get("organization") or {}
    verbatim = row.get("verbatim") or {}
    doc_type = org.get("doc_type") or row.get("doc_type") or "legislacao"
    meta = dict(verbatim.get("meta") or row.get("meta") or {})
    organized = dict(org.get("organized") or row.get("organized") or {})
    body = verbatim.get("dispositivo_legal") or verbatim.get("texto") or row.get("body")
    return {
        "external_id": str(row.get("external_id") or row.get("id") or "").strip(),
        "doc_type": doc_type,
        "source_system": verbatim.get("source_system") or row.get("source_system"),
        "title": verbatim.get("titulo") or row.get("title"),
        "body": body,
        "meta": meta,
        "organized": organized,
    }


def merge_sources(sources: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for batch in sources:
        for row in batch:
            eid = str(row.get("external_id") or "").strip()
            if not eid:
                continue
            if eid not in by_id:
                order.append(eid)
            by_id[eid] = row
    return [by_id[eid] for eid in order]


def export_corpus(repo_root: Path, out_path: Path) -> int:
    inbox = _load_jsonl(repo_root / "data/crawl_inbox/corpus.jsonl")
    manifest = _load_jsonl(repo_root / "preview/demo-manifest.jsonl")
    repository = _load_jsonl(repo_root / "repository/lex_corpus.jsonl")
    organized_latest = _load_jsonl(repo_root / "data/organized/latest/manifest.jsonl")

    normalized = merge_sources(
        [
            [_normalize_inbox_row(r) for r in inbox],
            [_normalize_manifest_row(r) for r in manifest],
            [_normalize_inbox_row(r) for r in repository],
            [_normalize_manifest_row(r) for r in organized_latest],
        ]
    )
    normalized = [r for r in normalized if r.get("external_id")]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "count": len(normalized),
        "documents": normalized,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {len(normalized)} documento(s) → {out_path}")
    return len(normalized)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="Exporta corpus Lex para web/lex/data/corpus.json")
    p.add_argument(
        "--out",
        type=Path,
        default=repo_root / "web/lex/data/corpus.json",
        help="Destino JSON (default: web/lex/data/corpus.json)",
    )
    args = p.parse_args()
    n = export_corpus(repo_root, args.out.expanduser().resolve())
    return 0 if n >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
