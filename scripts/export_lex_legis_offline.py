#!/usr/bin/env python3
"""Exporta catálogo e textos de legislação (Planalto + Rideel) para fallback offline do Lex."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
OUT_CATALOG = REPO / "web" / "lex" / "data" / "legis_catalog.json"
OUT_BODIES = REPO / "web" / "lex" / "data" / "legis_bodies.json"
AGU_DIR = REPO / "data" / "legislacao_agu"
SOURCES = ["planalto", "rideel_vademecum"]
PLANALTO_SOURCE = "planalto"


def read_config() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    if url and key:
        return url.rstrip("/"), key
    cfg = REPO / "web" / "lex" / "js" / "config.js"
    text = cfg.read_text(encoding="utf-8")
    url_m = re.search(r'supabaseUrl:\s*"([^"]+)"', text)
    key_m = re.search(r'supabaseAnonKey:\s*\n?\s*"([^"]+)"', text)
    url = (url_m.group(1) if url_m else "").rstrip("/")
    key = key_m.group(1) if key_m else ""
    if not url or not key:
        print("Defina SUPABASE_URL e SUPABASE_ANON_KEY ou use web/lex/js/config.js", file=sys.stderr)
        sys.exit(1)
    return url, key


def rpc(client: httpx.Client, name: str, body: dict) -> object:
    r = client.post(f"/rest/v1/rpc/{name}", json=body, timeout=180)
    r.raise_for_status()
    return r.json()


def list_catalog(client: httpx.Client, source: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        batch = rpc(client, "list_norma_document_catalog", {
            "p_source": source,
            "p_limit": 500,
            "p_offset": offset,
        })
        if not batch:
            break
        rows.extend(batch)
        offset += 500
        if len(batch) < 500:
            break
    return rows


def map_catalog_row(row: dict) -> dict:
    meta = row.get("metadata") or {}
    doc_url = row.get("url") or row.get("doc_key") or ""
    source = row.get("source") or "planalto"
    return {
        "external_id": f"{source}::{row.get('doc_key') or doc_url}",
        "doc_type": "legislacao",
        "source_system": source,
        "doc_key": row.get("doc_key") or doc_url,
        "title": meta.get("titulo") or row.get("doc_key") or doc_url,
        "resumo": meta.get("resumo"),
        "url": doc_url,
        "meta": meta,
        "organized": {
            "secao_lei_seca": meta.get("secao_lei_seca"),
            "corpus": meta.get("corpus"),
        },
        "chunk_count": row.get("chunk_count"),
    }


def fetch_body(client: httpx.Client, row: dict) -> str:
    doc_url = row.get("url") or row.get("doc_key") or ""
    source = row.get("source") or "planalto"
    doc_key = row.get("doc_key") or doc_url
    for candidate in (doc_url, doc_key):
        if not candidate:
            continue
        try:
            text = rpc(client, "get_norma_document_chunks", {
                "p_source": source,
                "p_url": candidate,
            })
            if isinstance(text, str) and len(text.strip()) >= 80:
                return text
        except httpx.HTTPError:
            pass
    try:
        text = rpc(client, "get_norma_document_text", {
            "p_source": source,
            "p_doc_key": doc_key,
        })
        if isinstance(text, str) and len(text.strip()) >= 80:
            return text
    except httpx.HTTPError:
        pass
    return ""


def _iter_agu_jsonl(path: Path):
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
    from naintegra_lex_agent.norma_chunks import normalize_norma_url

    files = sorted(input_dir.glob("*.jsonl"))
    if not files:
        return []
    by_url: dict[str, dict] = {}
    for fp in files:
        for rec in _iter_agu_jsonl(fp):
            url = normalize_norma_url(str(rec.get("url") or ""))
            if not url:
                continue
            prev = by_url.get(url)
            body_len = len(str(rec.get("content") or rec.get("summary") or ""))
            prev_len = len(str((prev or {}).get("content") or (prev or {}).get("summary") or ""))
            if not prev or body_len > prev_len:
                by_url[url] = rec
    return list(by_url.values())


def map_agu_catalog_row(rec: dict) -> dict:
    from naintegra_lex_agent.legal_text import pick_display_title
    from naintegra_lex_agent.norma_chunks import legis_meta_from_url, normalize_norma_url

    url = normalize_norma_url(str(rec.get("url") or ""))
    meta_url = legis_meta_from_url(url)
    titulo = pick_display_title(rec) or str(rec.get("title") or "").strip()
    if titulo and meta_url.get("titulo"):
        titulo = meta_url["titulo"]
    tags = rec.get("tags") or []
    meta = {
        "titulo": titulo or url,
        "secao_lei_seca": meta_url.get("secao_lei_seca") or "Legislação Especial",
        "corpus": "legislacao_agu",
        "collection": rec.get("collection") or "legislacao_agu",
        "carreiras_agu": [
            t
            for t in tags
            if isinstance(t, str)
            and not t.startswith("agu:")
            and t not in ("planalto", "agu")
        ],
        "legal_act_type": rec.get("legal_act_type"),
    }
    return {
        "external_id": f"{PLANALTO_SOURCE}::{url}",
        "doc_type": "legislacao",
        "source_system": PLANALTO_SOURCE,
        "doc_key": url,
        "title": meta["titulo"],
        "resumo": None,
        "url": url,
        "meta": meta,
        "organized": {
            "secao_lei_seca": meta["secao_lei_seca"],
            "corpus": meta["corpus"],
        },
        "chunk_count": None,
    }


def merge_agu_legislacao(
    client: httpx.Client,
    catalog_docs: list[dict],
    bodies: dict[str, str],
) -> tuple[int, int]:
    """Inclui normas AGU coletadas que ainda não aparecem na MV do catálogo."""
    from naintegra_lex_agent.norma_chunks import normalize_norma_url

    records = load_agu_records(AGU_DIR)
    if not records:
        return 0, 0

    known = {normalize_norma_url(d.get("url") or d.get("doc_key") or "") for d in catalog_docs}
    added = fail = 0
    for rec in records:
        mapped = map_agu_catalog_row(rec)
        key = normalize_norma_url(mapped["doc_key"])
        if key in known:
            continue
        row = {
            "source": PLANALTO_SOURCE,
            "url": mapped["url"],
            "doc_key": mapped["doc_key"],
        }
        text = fetch_body(client, row)
        if not text:
            fail += 1
            continue
        catalog_docs.append(mapped)
        bodies[mapped["doc_key"]] = text
        bodies[mapped["url"]] = text
        ext = mapped.get("external_id")
        if ext:
            bodies[ext] = text
        known.add(key)
        added += 1
    return added, fail


def main() -> int:
    sb_url, sb_key = read_config()
    headers = {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Content-Type": "application/json",
    }
    generated = datetime.now(timezone.utc).isoformat()
    catalog_docs: list[dict] = []
    bodies: dict[str, str] = {}
    ok = fail = 0

    with httpx.Client(base_url=sb_url, headers=headers, timeout=180) as client:
        for source in SOURCES:
            print(f"[…] catálogo {source}")
            rows = list_catalog(client, source)
            print(f"    {len(rows)} documento(s)")
            for row in rows:
                mapped = map_catalog_row(row)
                catalog_docs.append(mapped)
                doc_url = mapped.get("url") or mapped.get("doc_key") or ""
                if not doc_url:
                    continue
                text = fetch_body(client, row)
                if not text:
                    fail += 1
                    continue
                bodies[mapped["doc_key"]] = text
                bodies[doc_url] = text
                ext = mapped.get("external_id")
                if ext:
                    bodies[ext] = text
                ok += 1
                if ok % 25 == 0:
                    print(f"    {ok} textos…", flush=True)

        if AGU_DIR.is_dir():
            print("[…] legislação AGU (coleta recente)")
            agu_ok, agu_fail = merge_agu_legislacao(client, catalog_docs, bodies)
            ok += agu_ok
            fail += agu_fail
            print(f"    +{agu_ok} documento(s) AGU ({agu_fail} sem texto)")

    OUT_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    OUT_CATALOG.write_text(
        json.dumps(
            {
                "generated_at": generated,
                "count": len(catalog_docs),
                "documents": catalog_docs,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    OUT_BODIES.write_text(
        json.dumps(
            {
                "generated_at": generated,
                "count": ok,
                "bodies": bodies,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"[OK] catálogo → {OUT_CATALOG} ({len(catalog_docs)} docs)")
    print(f"[OK] textos → {OUT_BODIES} ({ok} ok, {fail} falhas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
