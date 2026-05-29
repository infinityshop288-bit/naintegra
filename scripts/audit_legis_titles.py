#!/usr/bin/env python3
"""Audita títulos/resumos do Lex contra a ementa do texto Planalto em legis_bodies.json.

Uso:
  python3 scripts/audit_legis_titles.py
  python3 scripts/audit_legis_titles.py --min-ratio 0.3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "web" / "lex" / "data" / "legis_catalog.json"
BODIES = ROOT / "web" / "lex" / "data" / "legis_bodies.json"


def extract_ementa(text: str) -> str:
    if text.startswith("#"):
        text = "\n".join(text.split("\n")[3:])
    flat = re.sub(r"\s+", " ", text[:4000])
    for pat in (
        r"((?:Dispõe|Institui|Altera|Regula|Define|Estabelece|Cria|Autoriza|Consolida|Revoga|Introduz|Limita|Fixa|Aprova)[^.]{12,220}\.)",
        r"(Lei das? [^.]{8,100}\.)",
    ):
        m = re.search(pat, flat, re.I)
        if m and "Vide Lei" not in m.group(1)[:40]:
            return m.group(1).strip()
    return ""


def body_for(url: str, bodies: dict[str, str]) -> str:
    np = url.split("planalto.gov.br")[-1].lower() if url else ""
    for k, v in bodies.items():
        if np and np in k.lower():
            return v
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita título/resumo × ementa Planalto")
    parser.add_argument(
        "--min-ratio",
        type=float,
        default=0.28,
        help="Similaridade mínima entre resumo e ementa (abaixo = suspeito)",
    )
    args = parser.parse_args()

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    bodies = json.loads(BODIES.read_text(encoding="utf-8")).get("bodies") or {}

    suspects: list[tuple[float, str, str, str]] = []
    for doc in catalog.get("documents") or []:
        url = str(doc.get("url") or "")
        if "planalto" not in url.lower():
            continue
        title = str(doc.get("title") or "")
        resumo = str(doc.get("resumo") or "")
        body = body_for(url, bodies)
        if not body:
            continue
        em = extract_ementa(body)
        if not em:
            continue
        a = re.sub(r"[^a-záéíóúãõç\s]", "", (resumo or title).lower())
        b = re.sub(r"[^a-záéíóúãõç\s]", "", em.lower())
        if len(a) < 12:
            continue
        ratio = SequenceMatcher(None, a[:140], b[:140]).ratio()
        if ratio < args.min_ratio:
            suspects.append((ratio, title, em[:120], url))

    suspects.sort(key=lambda x: x[0])
    print(f"=== Auditoria título/resumo × ementa (Planalto) ===")
    print(f"Documentos Planalto: {sum(1 for d in catalog.get('documents', []) if 'planalto' in str(d.get('url','')).lower())}")
    print(f"Suspeitos (ratio < {args.min_ratio}): {len(suspects)}")
    for ratio, title, em, url in suspects[:40]:
        print(f"\n{ratio:.2f} | {title}")
        print(f"  ementa: {em}")
        print(f"  {url[-72:]}")
    return 1 if suspects else 0


if __name__ == "__main__":
    raise SystemExit(main())
