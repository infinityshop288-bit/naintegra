#!/usr/bin/env python3
"""Atualiza legis_bodies.json (e catálogo) a partir do texto compilado do Planalto."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import importlib.util

from naintegra_lex_agent.planalto_legis import fetch_planalto_text  # noqa: E402

_meta_path = ROOT / "scripts" / "build_legis_known_meta.py"
_spec = importlib.util.spec_from_file_location("build_legis_known_meta", _meta_path)
meta_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(meta_mod)

KNOWN = meta_mod.KNOWN
match_key = meta_mod.match_key
patch_bodies = meta_mod.patch_bodies
patch_catalog = meta_mod.patch_catalog
patch_summaries = meta_mod.patch_summaries
build_entries = meta_mod.build_entries

BODIES = ROOT / "web" / "lex" / "data" / "legis_bodies.json"
CATALOG = ROOT / "web" / "lex" / "data" / "legis_catalog.json"

DEFAULT_URLS = [
    "http://www.planalto.gov.br/ccivil_03/leis/l8069.htm",
    "http://www.planalto.gov.br/ccivil_03/_ato2007-2010/2008/lei/l11671.htm",
    "http://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/l14965.htm",
    "http://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/l15040.htm",
]


def catalog_urls() -> dict[str, str]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for doc in data.get("documents", []):
        url = doc.get("url") or ""
        if url:
            out[url] = url
            out[url.replace("https://", "http://")] = url
            out[url.replace("http://", "https://")] = url
    return out


def main() -> int:
    urls = sys.argv[1:] or DEFAULT_URLS
    entries = build_entries()
    patch_catalog(entries)
    patch_summaries(entries)

    data = json.loads(BODIES.read_text(encoding="utf-8"))
    bodies: dict[str, str] = data.get("bodies") or {}
    url_map = catalog_urls()
    changed = 0

    for planalto_url in urls:
        fetched = fetch_planalto_text(planalto_url)
        arts = len(re.findall(r"\bArt\.?\s*\d", fetched.text))
        if arts < 5:
            print(f"[WARN] {planalto_url}: poucos artigos ({arts})", file=sys.stderr)

        key = match_key(planalto_url)
        titulo = entries.get(key or "", {}).get("titulo") if key else None
        if not titulo:
            titulo = KNOWN.get(key or "", ("", "", ""))[0] if key else planalto_url

        target_url = url_map.get(planalto_url) or url_map.get(planalto_url.replace("http://", "https://"))
        if not target_url:
            print(f"[SKIP] URL não está no catálogo offline: {planalto_url}", file=sys.stderr)
            continue

        bodies[target_url] = f"# {titulo}\n\nFonte: {target_url}\n\n{fetched.text}"
        changed += 1
        print(f"[OK] {titulo} — {fetched.char_count} chars, ~{arts} arts → {target_url}")

    if changed:
        data["bodies"] = bodies
        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        data["count"] = len(bodies)
        BODIES.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        patch_bodies(entries)
        print(f"Atualizado {changed} corpo(s) em {BODIES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
