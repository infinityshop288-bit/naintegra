"""Busca no acervo local (lei, júris, doutrina, provas)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from naintegra_lex_agent.acervo_varredura.enrich import strip_html
from naintegra_lex_agent.acervo_varredura.scan import summary_key
from naintegra_lex_agent.acervo_varredura.paths import (
    DOUTRINA_CATALOG,
    JURIS_RESUMOS,
    LEGIS_BODIES,
    LEGIS_CATALOG,
    LEGIS_SUMMARIES,
    SUMULAS_CATALOG,
    TEMAS_CATALOG,
)

ROOT = Path(__file__).resolve().parents[3]
PROVAS = ROOT / "web" / "lex" / "data" / "provas_juridicas.json"
_TOKEN = re.compile(r"[a-záéíóúâêôãõç0-9]{2,}", re.I)


def _load(path: Path) -> Any:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _tokens(q: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(q or "") if t]


def _score(blob: str, tokens: list[str]) -> int:
    text = (blob or "").lower()
    if not tokens or not text:
        return 0
    score = 0
    for tok in tokens:
        if tok in text:
            score += 4 if len(tok) > 3 else 2
    joined = " ".join(tokens)
    if joined and joined in text:
        score += 8
    return score


@lru_cache(maxsize=1)
def _index() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    legis = _load(LEGIS_CATALOG)
    summaries = (_load(LEGIS_SUMMARIES) or {}).get("summaries") or {}
    for doc in legis.get("documents") or []:
        url = str(doc.get("url") or doc.get("doc_key") or "")
        sm = summaries.get(summary_key(url)) or {}
        items.append(
            {
                "id": str(doc.get("external_id") or url),
                "kind": "legislacao",
                "title": str(doc.get("title") or sm.get("titulo") or url),
                "snippet": str(doc.get("resumo") or sm.get("resumo") or ""),
                "url": url,
            }
        )
    for entry in (_load(SUMULAS_CATALOG) or {}).get("sumulas") or []:
        items.append(
            {
                "id": str(entry.get("external_id") or entry.get("lex_route_id") or ""),
                "kind": "sumula",
                "title": str(entry.get("title") or ""),
                "snippet": strip_html(str(entry.get("enunciado") or entry.get("preview") or "")),
                "url": str(entry.get("url") or ""),
            }
        )
    for entry in (_load(TEMAS_CATALOG) or {}).get("temas") or []:
        items.append(
            {
                "id": str(entry.get("external_id") or entry.get("lex_route_id") or ""),
                "kind": "tema",
                "title": str(entry.get("title") or ""),
                "snippet": strip_html(str(entry.get("preview") or ""))[:400],
                "url": str(entry.get("url") or ""),
            }
        )
    dout = _load(DOUTRINA_CATALOG)
    for doc in dout.get("documents") or []:
        items.append(
            {
                "id": str(doc.get("external_id") or ""),
                "kind": "doutrina",
                "title": str(doc.get("title") or ""),
                "snippet": str(doc.get("body") or "")[:280],
                "url": "",
            }
        )
    provas = _load(PROVAS)
    for doc in provas.get("documents") or []:
        items.append(
            {
                "id": str(doc.get("external_id") or ""),
                "kind": "prova",
                "title": str(doc.get("title") or (doc.get("organized") or {}).get("materia") or "Questão"),
                "snippet": str(doc.get("body") or "")[:280],
                "url": "",
            }
        )
    return items


def search_acervo(query: str, *, kind: str = "all", limit: int = 8) -> list[dict[str, Any]]:
    tokens = _tokens(query)
    if not tokens:
        return []
    wanted = (kind or "all").lower()
    groups = {
        "legislacao": {"legislacao"},
        "lei": {"legislacao"},
        "juris": {"sumula", "tema"},
        "jurisprudencia": {"sumula", "tema"},
        "doutrina": {"doutrina"},
        "prova": {"prova"},
        "provas": {"prova"},
    }
    allow = groups.get(wanted)
    hits: list[tuple[int, dict[str, Any]]] = []
    for item in _index():
        if allow and item["kind"] not in allow:
            continue
        blob = f"{item['title']}\n{item['snippet']}"
        score = _score(blob, tokens)
        if score <= 0:
            continue
        hits.append((score, item))
    hits.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, item in hits[: max(1, min(limit, 20))]:
        row = dict(item)
        row["score"] = score
        out.append(row)
    return out


def read_document(doc_id: str, *, max_chars: int = 6000) -> dict[str, Any] | None:
    needle = (doc_id or "").strip()
    if not needle:
        return None
    for item in _index():
        if needle not in {item["id"], item.get("url"), item["id"].split("::")[-1]} and needle not in item["id"]:
            continue
        text = item.get("snippet") or ""
        if item["kind"] == "legislacao":
            bodies = (_load(LEGIS_BODIES) or {}).get("bodies") or {}
            url = item.get("url") or ""
            text = str(bodies.get(url) or bodies.get(f"planalto::{url}") or text)
        elif item["kind"] == "doutrina":
            for doc in (_load(DOUTRINA_CATALOG) or {}).get("documents") or []:
                if str(doc.get("external_id") or "") == item["id"]:
                    text = str(doc.get("body") or text)
                    break
        elif item["kind"] == "prova":
            for doc in (_load(PROVAS) or {}).get("documents") or []:
                if str(doc.get("external_id") or "") == item["id"]:
                    meta = doc.get("meta") or {}
                    text = f"{doc.get('body')}\n\nGabarito: {meta.get('gabarito_banca')}\n{meta.get('resposta_ia') or ''}"
                    break
        elif item["kind"] in {"sumula", "tema"}:
            teses = ((_load(JURIS_RESUMOS) or {}).get("items") or {}).get(item["id"]) or {}
            extra = teses.get("tese") or ""
            text = f"{item.get('snippet')}\n\n{extra}".strip()
        return {
            "id": item["id"],
            "kind": item["kind"],
            "title": item["title"],
            "text": text[:max_chars],
        }
    return None
