"""Monta a fila de atualização a partir dos catálogos locais."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .enrich import strip_html
from .paths import (
    DOUTRINA_CATALOG,
    DOUTRINA_RESUMOS,
    JURIS_RESUMOS,
    LEGIS_BODIES,
    LEGIS_CATALOG,
    LEGIS_SUMMARIES,
    SUMULAS_CATALOG,
    TEMAS_CATALOG,
)
from naintegra_lex_agent.provas_juridicas.status import write_json_atomic


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any, *, indent: int | None = 2) -> None:
    write_json_atomic(path, payload, indent=indent)


def summary_key(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        path = urlparse(raw).path
    except ValueError:
        path = raw.split("?")[0]
    return path.rstrip("/").lower()


def legis_items() -> list[dict[str, Any]]:
    raw = load_json(LEGIS_CATALOG, {})
    return [d for d in (raw.get("documents") or []) if isinstance(d, dict)]


def body_for(url: str, bodies: dict[str, str]) -> str:
    if not url:
        return ""
    return str(bodies.get(url) or bodies.get(f"planalto::{url}") or "")


def queue_legislacao(summaries: dict[str, Any], resumos_ia: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for doc in legis_items():
        url = str(doc.get("url") or doc.get("doc_key") or "")
        key = summary_key(url)
        if key and key in resumos_ia:
            continue
        cached = summaries.get(key) or {}
        if cached.get("elaboracao") == "ia" and len(str(cached.get("resumo") or "")) >= 40:
            continue
        out.append(
            {
                "kind": "legislacao",
                "id": str(doc.get("external_id") or url),
                "url": url,
                "key": key,
                "title": str(doc.get("title") or cached.get("titulo") or url),
                "secao": str((doc.get("organized") or {}).get("secao_lei_seca") or cached.get("secao") or ""),
            }
        )
    return out


def queue_jurisprudencia(done: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    sums = load_json(SUMULAS_CATALOG, {})
    for entry in sums.get("sumulas") or []:
        eid = str(entry.get("external_id") or entry.get("lex_route_id") or "")
        if not eid or eid in done:
            continue
        texto = strip_html(str(entry.get("enunciado") or entry.get("preview") or ""))
        if len(texto) < 20:
            continue
        out.append(
            {
                "kind": "jurisprudencia",
                "id": eid,
                "title": str(entry.get("title") or eid),
                "texto": texto,
                "subtipo": "sumula",
            }
        )
    temas = load_json(TEMAS_CATALOG, {})
    for entry in temas.get("temas") or []:
        eid = str(entry.get("external_id") or entry.get("lex_route_id") or "")
        if not eid or eid in done:
            continue
        texto = strip_html(str(entry.get("preview") or entry.get("title") or ""))
        if len(texto) < 20:
            continue
        out.append(
            {
                "kind": "jurisprudencia",
                "id": eid,
                "title": str(entry.get("title") or eid),
                "texto": texto,
                "subtipo": "tema",
            }
        )
    return out


def queue_doutrina(done: set[str], *, limit: int = 400) -> list[dict[str, Any]]:
    raw = load_json(DOUTRINA_CATALOG, {})
    out: list[dict[str, Any]] = []
    for doc in raw.get("documents") or []:
        if len(out) >= limit:
            break
        if not isinstance(doc, dict):
            continue
        eid = str(doc.get("external_id") or "")
        if not eid or eid in done:
            continue
        body = str(doc.get("body") or "")
        if len(body.strip()) < 80:
            continue
        out.append(
            {
                "kind": "doutrina",
                "id": eid,
                "title": str(doc.get("title") or eid),
                "texto": body,
            }
        )
    return out


def load_sidecar_ids(path: Path) -> set[str]:
    raw = load_json(path, {})
    items = raw.get("items") or raw
    if isinstance(items, dict):
        return {str(k) for k, v in items.items() if isinstance(v, dict) and v.get("elaboracao") == "ia"}
    return set()


def existing_ia_summary_keys() -> set[str]:
    summaries = load_json(LEGIS_SUMMARIES, {}).get("summaries") or {}
    return {k for k, v in summaries.items() if isinstance(v, dict) and v.get("elaboracao") == "ia"}


def build_queue() -> list[dict[str, Any]]:
    summaries = load_json(LEGIS_SUMMARIES, {}).get("summaries") or {}
    legis = queue_legislacao(summaries, existing_ia_summary_keys())
    juris = queue_jurisprudencia(load_sidecar_ids(JURIS_RESUMOS))
    dout = queue_doutrina(load_sidecar_ids(DOUTRINA_RESUMOS))
    return legis + juris + dout


def peek_count(path: Path, fallback: int = 0) -> int:
    if not path.is_file():
        return fallback
    head = path.read_text(encoding="utf-8", errors="replace")[:800]
    match = re.search(r'"count"\s*:\s*(\d+)', head)
    return int(match.group(1)) if match else fallback


def catalog_counts() -> dict[str, int]:
    return {
        "legislacao": peek_count(LEGIS_CATALOG, len(legis_items())),
        "sumulas": peek_count(SUMULAS_CATALOG),
        "temas": peek_count(TEMAS_CATALOG),
        "doutrina": peek_count(DOUTRINA_CATALOG),
        "legis_ia": len(existing_ia_summary_keys()),
        "juris_ia": peek_count(JURIS_RESUMOS, len(load_sidecar_ids(JURIS_RESUMOS))),
        "doutrina_ia": peek_count(DOUTRINA_RESUMOS, len(load_sidecar_ids(DOUTRINA_RESUMOS))),
    }


_bodies: dict[str, str] | None = None


def load_bodies(*, force: bool = False) -> dict[str, str]:
    global _bodies
    if _bodies is None or force:
        _bodies = dict((load_json(LEGIS_BODIES, {}) or {}).get("bodies") or {})
    return _bodies


def excerpt_from_bodies(url: str) -> str:
    return body_for(url, load_bodies())
