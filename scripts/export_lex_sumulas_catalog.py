#!/usr/bin/env python3
"""Exporta catálogo completo de súmulas (STF, STJ, STF vinculantes, TSE) para web/lex/data/sumulas_catalog.json."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "web" / "lex" / "data" / "sumulas_catalog.json"
BASE = "https://informativos.trilhante.com.br"

LISTINGS = [
    ("STF", "/sumulas/stf"),
    ("STJ", "/sumulas/stj"),
    ("STF", "/sumulas/stf-vinculante"),
    ("TSE", "/sumulas/tse"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NaIntegraLex/1.0; +https://naintegracursos.com.br/lex)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

ITEM_RE = re.compile(r'item="(\{&quot;id&quot;[^"]+)"', re.I)


def route_id(tribunal: str, numero: str, vinculante: bool) -> str:
    tr = tribunal.lower()
    if vinculante:
        return f"sumula-{tr}-sv-{numero}"
    return f"sumula-{tr}-{numero}"


def slug_to_url(slug: str, listing_path: str) -> str:
    slug = slug.strip("/")
    base = listing_path.rstrip("/")
    return f"{BASE}{base}/{slug}"


def parse_page(html: str, listing_path: str, default_tribunal: str) -> list[dict]:
    items: list[dict] = []
    for raw in ITEM_RE.findall(html):
        try:
            data = json.loads(unescape(raw))
        except json.JSONDecodeError:
            continue
        if data.get("type") not in ("sumula", "sumula-vinculante"):
            continue
        name = str(data.get("name") or "")
        vm = re.search(r"Vinculante\s+(\d+)", name, re.I)
        sm = re.search(r"S[úu]mula\s+(\d+)", name, re.I)
        if vm:
            num = vm.group(1)
            vinculante = True
            label = f"SV {num}"
        elif sm:
            num = sm.group(1)
            vinculante = "vinculante" in listing_path
            label = f"SV {num}" if vinculante else f"Súmula {num}"
        else:
            num = str(data.get("position") or "")
            if not num.isdigit():
                continue
            vinculante = "vinculante" in listing_path
            label = f"SV {num}" if vinculante else f"Súmula {num}"

        tribunal = str(data.get("institution") or default_tribunal).upper()
        slug = str(data.get("slug") or f"sumula-{num}-{tribunal.lower()}")
        url = slug_to_url(slug, listing_path)
        preview = str(data.get("destaque_oficial") or data.get("destaque") or "").strip()
        rid = route_id(tribunal, num, vinculante)
        items.append(
            {
                "lex_route_id": rid,
                "url": url,
                "title": f"{label} — {tribunal}",
                "tribunal": tribunal,
                "numero": num,
                "vinculante": vinculante,
                "preview": preview[:800],
                "doc_type": "sumula",
                "source_system": "trilhante_informativo",
                "doc_key": url,
                "external_id": f"trilhante_informativo::{url}",
            }
        )
    return items


def fetch_listing(client: httpx.Client, path: str, tribunal: str) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    page = 1
    while page <= 40:
        url = f"{BASE}{path}" if page == 1 else f"{BASE}{path}?page={page}"
        res = client.get(url)
        res.raise_for_status()
        batch = parse_page(res.text, path, tribunal)
        if not batch:
            break
        for item in batch:
            if item["lex_route_id"] in seen:
                continue
            seen.add(item["lex_route_id"])
            out.append(item)
        page += 1
    return out


def main() -> int:
    all_items: list[dict] = []
    seen_ids: set[str] = set()
    errors: list[str] = []

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=60.0) as client:
        for tribunal, path in LISTINGS:
            try:
                batch = fetch_listing(client, path, tribunal)
                for item in batch:
                    if item["lex_route_id"] in seen_ids:
                        continue
                    seen_ids.add(item["lex_route_id"])
                    all_items.append(item)
                print(f"{path}: {len(batch)} súmulas")
            except Exception as exc:
                errors.append(f"{path}: {exc}")
                print(f"ERRO {path}: {exc}", file=sys.stderr)

    all_items.sort(
        key=lambda x: (
            x["tribunal"],
            0 if x["vinculante"] else 1,
            int(x["numero"]),
        )
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(all_items),
        "errors": errors,
        "sumulas": all_items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exportadas {len(all_items)} súmulas -> {OUT}")
    return 0 if all_items else 1


if __name__ == "__main__":
    raise SystemExit(main())
