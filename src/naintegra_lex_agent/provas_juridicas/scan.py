"""Varre o banco local e monta o catálogo de provas jurídicas (últimos 2 anos)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ai_answers import finalize_answer
from .careers import PROVA_YEARS, career_tags, in_year_window, origem_carreira
from .citations import lookup_dispositivos, lookup_jurisprudencia
from .status import write_json_atomic

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SRC = ROOT / "web" / "lex" / "data" / "questoes_catalog.json"
DEFAULT_OUT = ROOT / "web" / "lex" / "data" / "provas_juridicas.json"


def _blob(row: dict[str, Any]) -> str:
    meta = row.get("meta") or {}
    parts = [
        row.get("body") or "",
        row.get("title") or "",
        meta.get("comentario") or "",
        meta.get("explicacao") or "",
        str(meta.get("gabarito") or ""),
        meta.get("assunto") or "",
        (row.get("organized") or {}).get("materia") or "",
    ]
    return "\n".join(str(p) for p in parts if p)


def scan_rows(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in documents:
        if not in_year_window(row):
            continue
        tags = career_tags(row)
        if not tags:
            continue
        meta = dict(row.get("meta") or {})
        org = dict(row.get("organized") or {})
        blob = _blob(row)
        dispositivos = lookup_dispositivos(blob, materia=str(org.get("materia") or ""))
        juris = lookup_jurisprudencia(blob)
        gabarito = meta.get("gabarito") or meta.get("resposta_correta") or ""
        resposta_banca = str(meta.get("comentario") or meta.get("explicacao") or gabarito or "").strip()
        built = {
            "external_id": f"pj::{str(row.get('external_id') or '').removeprefix('qb::')}",
            "source_id": row.get("external_id"),
            "doc_type": row.get("doc_type"),
            "source_system": "provas_juridicas",
            "carreiras_prova": tags,
            "title": row.get("title"),
            "body": row.get("body"),
            "meta": {
                "alternativas": meta.get("alternativas") or [],
                "gabarito_banca": gabarito,
                "resposta_banca": resposta_banca,
                "resposta_ia": "",
                "dispositivos": dispositivos,
                "jurisprudencia": juris,
                "carreira_origem": origem_carreira(row),
                "assunto": meta.get("assunto"),
                "fonte": meta.get("fonte"),
                "elaboracao": "pendente",
            },
            "organized": {
                "banca": org.get("banca"),
                "ano": org.get("ano"),
                "materia": org.get("materia"),
                "cargo": org.get("cargo"),
            },
        }
        out.append(built)
    return out


def _already_ia(row: dict[str, Any]) -> bool:
    meta = row.get("meta") or {}
    return meta.get("elaboracao") == "ia" and bool(str(meta.get("resposta_ia") or "").strip())


def enrich(
    rows: list[dict[str, Any]],
    *,
    use_ai: bool,
    ai_limit: int,
    model: str | None,
    ai_only_subjetivas: bool = False,
    skip_existing_ia: bool = True,
    on_progress: Any | None = None,
) -> list[dict[str, Any]]:
    remaining = ai_limit
    order = list(range(len(rows)))
    if use_ai:
        order.sort(key=lambda i: 0 if rows[i].get("doc_type") == "questoes_subjetivas" else 1)
    for idx in order:
        row = rows[idx]
        if skip_existing_ia and _already_ia(row):
            continue
        eligible = (not ai_only_subjetivas) or row.get("doc_type") == "questoes_subjetivas"
        want_ai = use_ai and eligible and remaining > 0
        text, kind = finalize_answer(row, use_ai=want_ai, model=model)
        row.setdefault("meta", {})
        row["meta"]["resposta_ia"] = text
        row["meta"]["elaboracao"] = kind
        if want_ai and kind == "ia":
            remaining -= 1
            logger.info("IA ok %s (%s restantes)", str(row.get("external_id") or "")[-12:], remaining)
        if on_progress is not None:
            on_progress(row, kind)
    return rows


def write_catalog(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "janela": {"de": min(PROVA_YEARS), "ate": max(PROVA_YEARS)},
        "count": len(rows),
        "documents": rows,
    }
    write_json_atomic(path, payload, indent=None)
    return path


def load_catalog(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    docs = list(raw.get("documents") or [])
    return [row for row in docs if isinstance(row, dict)]


def run(
    *,
    src: Path = DEFAULT_SRC,
    dest: Path = DEFAULT_OUT,
    use_ai: bool = False,
    ai_limit: int = 80,
    model: str | None = None,
    ai_only_subjetivas: bool = False,
    resume: bool = False,
    save_every: int = 1,
) -> Path:
    if resume and dest.is_file():
        rows = load_catalog(dest)
        logger.info("Retomando catálogo existente: %s questões em %s", len(rows), dest)
    else:
        raw = json.loads(src.read_text(encoding="utf-8"))
        docs = list(raw.get("documents") or [])
        rows = scan_rows(docs)
        logger.info("Varredura: %s questões nas carreiras-alvo (anos %s)", len(rows), PROVA_YEARS)
    pending = 0

    def _persist(_row: dict[str, Any], kind: str) -> None:
        nonlocal pending
        if kind != "ia":
            return
        pending += 1
        if pending >= max(1, save_every):
            write_catalog(dest, rows)
            pending = 0

    enrich(
        rows,
        use_ai=use_ai,
        ai_limit=ai_limit,
        model=model,
        ai_only_subjetivas=ai_only_subjetivas,
        skip_existing_ia=resume,
        on_progress=_persist if use_ai else None,
    )
    out = write_catalog(dest, rows)
    logger.info("Catálogo gravado em %s", out)
    return out
