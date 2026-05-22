#!/usr/bin/env python3
"""Exporta textos de jurisprudência/súmulas do Supabase para web/lex/data/juris_bodies.json."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "web" / "lex" / "data" / "juris_bodies.json"


def rpc(url: str, key: str, name: str, body: dict) -> object:
    req = urllib.request.Request(
        f"{url}/rest/v1/rpc/{name}",
        data=json.dumps(body).encode(),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    if not url or not key:
        cfg = REPO / "web" / "lex" / "js" / "config.js"
        text = cfg.read_text(encoding="utf-8")
        import re

        url_m = re.search(r'supabaseUrl:\s*"([^"]+)"', text)
        key_m = re.search(r'supabaseAnonKey:\s*\n?\s*"([^"]+)"', text)
        url = url or (url_m.group(1) if url_m else "")
        key = key or (key_m.group(1) if key_m else "")
    if not url or not key:
        print("Defina SUPABASE_URL e SUPABASE_ANON_KEY ou use web/lex/js/config.js", file=sys.stderr)
        sys.exit(1)

    offset = 0
    rows: list[dict] = []
    while True:
        batch = rpc(url, key, "list_norma_document_catalog", {
            "p_source": "trilhante_informativo",
            "p_limit": 500,
            "p_offset": offset,
        })
        if not batch:
            break
        rows.extend(batch)
        offset += 500
        if len(batch) < 500:
            break

    bodies: dict[str, str] = {}
    ok = fail = 0
    for row in rows:
        doc_url = row.get("url") or row.get("doc_key") or ""
        if not doc_url:
            continue
        p = doc_url.lower()
        if "/aprenda/" in p:
            continue
        if "/sumulas/" in p and "sumula-" not in p:
            continue
        if p.endswith("/principais-julgados") or p.endswith("/temas-stf") or p.endswith("/temas-stj"):
            continue
        if not any(x in p for x in ("sumula-", "tema-", "principais-julgados/", "jurisprudencia-em-teses")):
            continue
        try:
            text = rpc(url, key, "get_norma_document_chunks", {
                "p_source": row["source"],
                "p_url": doc_url,
            })
        except urllib.error.HTTPError as exc:
            fail += 1
            print("fail", doc_url[-60:], exc.code, file=sys.stderr)
            continue
        if not isinstance(text, str) or len(text.strip()) < 50:
            fail += 1
            continue
        bodies[row["doc_key"]] = text
        bodies[doc_url] = text
        ok += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(), "count": ok, "bodies": bodies}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Exportados {ok} textos ({fail} falhas) -> {OUT}")


if __name__ == "__main__":
    main()
