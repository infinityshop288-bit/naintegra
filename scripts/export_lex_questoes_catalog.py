#!/usr/bin/env python3
"""Exporta public.questoes_banco → web/lex/data/questoes_catalog.json (fallback offline do Lex)."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "web" / "lex" / "data" / "questoes_catalog.json"

COLS = (
    "id,carreira,banca,ano,disciplina,assunto,enunciado,"
    "alternativas,gabarito,explicacao,tipo,fonte"
)


def _cfg() -> tuple[str, str]:
    url = os.environ.get("LEX_AGENT_SUPABASE_URL", "").strip()
    key = os.environ.get("LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        # Mesmo projeto do Lex web (anon após sql/questoes_banco_anon_read.sql).
        url = "https://voybsggeedpwcfdadnzt.supabase.co"
        key = os.environ.get(
            "LEX_QUESTOES_EXPORT_ANON_KEY",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZveWJzZ2dlZWRwd2NmZGFkbnp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNzU2MTQsImV4cCI6MjA4ODc1MTYxNH0.dy5AgSd1VWdP4WLGXy5V89pA4jgHijngHJjScApOo70",
        )
    return url.rstrip("/"), key


def map_row(row: dict) -> dict:
    tipo = str(row.get("tipo") or "").lower()
    is_sub = tipo == "subjetiva"
    carreira = row.get("carreira") or ""
    cargo = carreira.replace("_", " ").title() if carreira else None
    alts = row.get("alternativas")
    alternativas: list[str] = []
    if isinstance(alts, dict):
        alternativas = [f"{k}) {v}" for k, v in sorted(alts.items())]
    elif isinstance(alts, list):
        alternativas = [str(a) for a in alts]
    return {
        "external_id": f"qb::{row['id']}",
        "doc_type": "questoes_subjetivas" if is_sub else "questoes_objetivas",
        "source_system": "naintegracursos",
        "title": " — ".join(
            p for p in (row.get("banca"), row.get("ano"), row.get("disciplina")) if p
        ),
        "body": row.get("enunciado"),
        "meta": {
            "alternativas": alternativas,
            "gabarito": row.get("gabarito"),
            "comentario": row.get("explicacao"),
            "assunto": row.get("assunto"),
            "fonte": row.get("fonte"),
            "carreira": carreira,
        },
        "organized": {
            "banca": row.get("banca"),
            "ano": row.get("ano"),
            "materia": row.get("disciplina"),
            "cargo": cargo,
        },
    }


def fetch_all(base: str, key: str) -> list[dict]:
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept-Profile": "public",
    }
    out: list[dict] = []
    offset = 0
    limit = 1000
    with httpx.Client(timeout=120.0) as client:
        while True:
            url = (
                f"{base}/rest/v1/questoes_banco"
                f"?select={COLS}&order=created_at.desc&limit={limit}&offset={offset}"
            )
            res = client.get(url, headers=headers)
            res.raise_for_status()
            batch = res.json()
            if not batch:
                break
            out.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
    return out


def main() -> int:
    base, key = _cfg()
    rows = fetch_all(base, key)
    docs = [map_row(r) for r in rows]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(docs),
        "documents": docs,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exportadas {len(docs)} questões → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
