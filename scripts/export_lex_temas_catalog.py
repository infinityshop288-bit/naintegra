#!/usr/bin/env python3
"""Exporta catálogo de temas (repercussão geral STF, repetitivos STJ/TST) para web/lex/data/temas_catalog.json."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "web" / "lex" / "data" / "temas_catalog.json"
BASE = "https://informativos.trilhante.com.br"

LISTINGS = [
    ("STF", "/temas-stf", "repercussao_geral"),
    ("STJ", "/temas-stj", "recurso_repetitivo"),
    ("TST", "/temas-tst", "recurso_repetitivo"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NaIntegraLex/1.0; +https://naintegracursos.com.br/lex)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

ITEM_RE = re.compile(r'item="(\{&quot;id&quot;[^"]+)"', re.I)
TEMA_TYPES = {"tese-stf", "tema-stj-rep", "tema-tst", "tema", "tese"}


def parse_numero(name: str, slug: str) -> str | None:
    for src in (name, slug):
        m = re.search(r"(?:Repetitivo\s+)?(?:Tema\s+)?(\d+)", src, re.I)
        if m:
            return m.group(1)
    m = re.search(r"tema(?:-repetitivo)?-(\d+)", slug, re.I)
    return m.group(1) if m else None


def route_id(tribunal: str, numero: str, repetitivo: bool) -> str:
    tr = tribunal.lower()
    if repetitivo and tr == "stj":
        return f"tema-{tr}-rep-{numero}"
    return f"tema-{tr}-{numero}"


def slug_to_url(slug: str, listing_path: str) -> str:
    slug = slug.strip("/")
    base = listing_path.rstrip("/")
    return f"{BASE}{base}/{slug}"


def tema_categoria(data: dict, default: str) -> str:
    if data.get("is_repercussao"):
        return "repercussao_geral"
    if data.get("is_repetitivo"):
        return "recurso_repetitivo"
    return default


def parse_page(html: str, listing_path: str, default_tribunal: str, default_categoria: str) -> list[dict]:
    items: list[dict] = []
    for raw in ITEM_RE.findall(html):
        try:
            data = json.loads(unescape(raw))
        except json.JSONDecodeError:
            continue
        item_type = str(data.get("type") or "")
        if item_type not in TEMA_TYPES and "tema" not in item_type.lower():
            continue

        name = str(data.get("name") or "")
        slug = str(data.get("slug") or "")
        numero = parse_numero(name, slug)
        if not numero:
            continue

        tribunal = str(data.get("institution") or default_tribunal).upper()
        repetitivo = "repetitivo" in item_type.lower() or "repetitivo" in slug.lower()
        categoria = tema_categoria(data, default_categoria)

        if repetitivo and tribunal == "STJ":
            label = f"Tema Repetitivo {numero}"
        elif categoria == "repercussao_geral" or tribunal == "STF":
            label = f"Tema {numero}"
        else:
            label = f"Tema {numero}"

        url = slug_to_url(slug, listing_path) if slug else ""
        if not url:
            continue

        preview = (
            str(data.get("destaque_oficial") or data.get("resumo_oficial") or data.get("destaque") or "")
            .strip()
        )
        rid = route_id(tribunal, numero, repetitivo and tribunal == "STJ")
        items.append(
            {
                "lex_route_id": rid,
                "url": url,
                "title": f"{label} — {tribunal}",
                "tribunal": tribunal,
                "numero": numero,
                "tema_categoria": categoria,
                "is_repercussao": bool(data.get("is_repercussao")),
                "is_repetitivo": bool(data.get("is_repetitivo")) or repetitivo,
                "preview": preview[:1200],
                "doc_type": "jurisprudencia",
                "source_system": "trilhante_informativo",
                "doc_key": url,
                "external_id": f"trilhante_informativo::{url}",
            }
        )
    return items


def fetch_listing(client: httpx.Client, path: str, tribunal: str, categoria: str) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    page = 1
    while page <= 60:
        url = f"{BASE}{path}" if page == 1 else f"{BASE}{path}?page={page}"
        res = client.get(url)
        res.raise_for_status()
        batch = parse_page(res.text, path, tribunal, categoria)
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
    stats: dict[str, int] = {}

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=60.0) as client:
        for tribunal, path, categoria in LISTINGS:
            try:
                batch = fetch_listing(client, path, tribunal, categoria)
                for item in batch:
                    if item["lex_route_id"] in seen_ids:
                        continue
                    seen_ids.add(item["lex_route_id"])
                    all_items.append(item)
                    cat = item["tema_categoria"]
                    stats[cat] = stats.get(cat, 0) + 1
                print(f"{path}: {len(batch)} temas")
            except Exception as exc:
                errors.append(f"{path}: {exc}")
                print(f"ERRO {path}: {exc}", file=sys.stderr)

    all_items.sort(
        key=lambda x: (
            x["tribunal"],
            0 if x["tema_categoria"] == "repercussao_geral" else 1,
            int(x["numero"]),
        )
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(all_items),
        "stats": stats,
        "errors": errors,
        "temas": all_items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exportados {len(all_items)} temas -> {OUT} ({stats})")
    return 0 if all_items else 1


if __name__ == "__main__":
    raise SystemExit(main())
