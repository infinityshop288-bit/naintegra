#!/usr/bin/env python3
"""Gera web/lex/data/sumulas_bodies.json a partir do catálogo (e opcionalmente do Trilhante)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
CATALOG = REPO / "web" / "lex" / "data" / "sumulas_catalog.json"
OUT = REPO / "web" / "lex" / "data" / "sumulas_bodies.json"
BASE = "https://informativos.trilhante.com.br"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NaIntegraLex/1.0; +https://naintegracursos.com.br/lex)",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

ITEM_RE = re.compile(r'item="(\{&quot;id&quot;[^"]+)"', re.I)


def strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", t).strip()


def label_for(entry: dict) -> str:
    if entry.get("vinculante"):
        return f"Súmula Vinculante {entry['numero']}"
    return f"Súmula {entry['numero']}"


def enunciado_from_entry(entry: dict) -> str:
    if entry.get("enunciado"):
        return str(entry["enunciado"]).strip()
    return strip_html(entry.get("preview") or "")


def body_for_entry(entry: dict, enunciado: str) -> str:
    tribunal = entry.get("tribunal") or "STF"
    title = entry.get("title") or f"{label_for(entry)} — {tribunal}"
    parts = [title, tribunal, ""]
    if enunciado:
        parts.append(enunciado)
    return "\n".join(parts).strip()


def fetch_enunciado(client: httpx.Client, url: str) -> str:
    res = client.get(url)
    res.raise_for_status()
    for raw in ITEM_RE.findall(res.text):
        try:
            data = json.loads(unescape(raw))
        except json.JSONDecodeError:
            continue
        if data.get("type") not in ("sumula", "sumula-vinculante"):
            continue
        dest = str(data.get("destaque_oficial") or data.get("destaque") or "").strip()
        if dest:
            return strip_html(dest) if "<" in dest else dest
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refetch-empty",
        action="store_true",
        help="Busca no Trilhante só entradas sem enunciado no catálogo",
    )
    args = parser.parse_args()

    if not CATALOG.is_file():
        print(f"Catálogo não encontrado: {CATALOG}", file=sys.stderr)
        return 1

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    entries = catalog.get("sumulas") or []
    bodies: dict[str, str] = {}
    empty_before = 0
    refetched = 0

    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=45.0) if args.refetch_empty else None

    try:
        for entry in entries:
            en = enunciado_from_entry(entry)
            if not en:
                empty_before += 1
                if client and entry.get("url"):
                    try:
                        en = fetch_enunciado(client, entry["url"])
                        if en:
                            refetched += 1
                            entry["enunciado"] = en
                            entry["preview"] = f"<p>{en}</p>"
                    except Exception as exc:
                        print(f"  falha {entry.get('lex_route_id')}: {exc}", file=sys.stderr)

            text = body_for_entry(entry, en)
            if not text:
                continue

            rid = entry.get("lex_route_id")
            url = entry.get("url") or entry.get("doc_key")
            doc_key = entry.get("doc_key") or url
            for key in (rid, url, doc_key):
                if key:
                    bodies[key] = text
    finally:
        if client:
            client.close()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries),
        "bodies": bodies,
        "empty_enunciado_before": empty_before,
        "refetched": refetched,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.refetch_empty and empty_before:
        catalog["generated_at"] = payload["generated_at"]
        CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Catálogo atualizado ({refetched} enunciados obtidos da web)")

    print(f"Gerados {len(bodies)} chaves de corpo para {len(entries)} súmulas -> {OUT}")
    if empty_before:
        print(f"  {empty_before} sem enunciado no catálogo ({refetched} recuperados)")
    return 0 if bodies else 1


if __name__ == "__main__":
    raise SystemExit(main())
