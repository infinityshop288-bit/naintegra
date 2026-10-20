"""Cita o dispositivo legal inteiro e a jurisprudência a partir do acervo Lex."""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
LEX_DATA = ROOT / "web" / "lex" / "data"

LAW_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("constituição federal de 1988", ("constituição federal", "constituição da república", "cf/88", "cf/1988", "cf 88")),
    ("decreto-lei 2.848/1940 — código penal", ("código penal", " do cp", " do cpb", "cp, ", "cp.")),
    ("decreto-lei 3.689/1941 — código de processo penal", ("código de processo penal", " do cpp", "cpp, ", "cpp.")),
    ("lei 13.105/2015 — código de processo civil", ("código de processo civil", " do cpc", "cpc/2015", "cpc, ", "cpc.")),
    ("lei 10.406/2002 — código civil", ("código civil", " do cc", "cc/2002", "cc, ")),
    ("decreto-lei 4.657/1942 — lindb", ("lindb", "lei de introdução")),
    ("lei 7.210/1984 — lei de execução penal", ("execução penal", " da lep", "lep")),
    ("lei 8.429/1992 — improbidade administrativa", ("improbidade", "lei 8.429", "lei nº 8.429")),
    ("lei 7.347/1985 — ação civil pública", ("ação civil pública", "lei 7.347", "lei da acp")),
    ("lei 12.016/2009 — mandado de segurança", ("mandado de segurança", "lei 12.016")),
    ("lei 8.137/1990 — crimes tributários", ("crimes tributários", "lei 8.137")),
)

ART_REF = re.compile(
    r"art(?:igo)?\.?\s*(\d{1,4})(?:º|o)?(?:\s*[-–]\s*[a-z])?",
    re.IGNORECASE,
)
SUMULA_REF = re.compile(
    r"s[uú]mula(?:\s+vinculante)?\s*(?:n[ºo.]?\s*)?(\d{1,4})",
    re.IGNORECASE,
)


def _fold(text: str) -> str:
    n = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in n if unicodedata.category(c) != "Mn")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _legis_index() -> tuple[list[dict[str, Any]], dict[str, str]]:
    catalog = _load_json(LEX_DATA / "legis_catalog.json")
    bodies = _load_json(LEX_DATA / "legis_bodies.json").get("bodies") or {}
    docs = list(catalog.get("documents") or [])
    return docs, {str(k): str(v) for k, v in bodies.items()}


@lru_cache(maxsize=1)
def _sumulas() -> list[dict[str, Any]]:
    data = _load_json(LEX_DATA / "sumulas_catalog.json")
    return list(data.get("sumulas") or [])


def _doc_key(doc: dict[str, Any]) -> str:
    return str(doc.get("doc_key") or doc.get("url") or "")


def _title_of(doc: dict[str, Any]) -> str:
    return str(doc.get("title") or "")


def find_law(hint: str, docs: list[dict[str, Any]]) -> dict[str, Any] | None:
    needle = _fold(hint)
    for doc in docs:
        if needle in _fold(_title_of(doc)):
            return doc
    return None


def resolve_law(text: str, docs: list[dict[str, Any]]) -> dict[str, Any] | None:
    folded = _fold(text)
    for title_hint, aliases in LAW_HINTS:
        if any(alias in folded for alias in aliases) or title_hint in folded:
            hit = find_law(title_hint, docs)
            if hit:
                return hit
    lei_num = re.search(r"lei\s+(?:n[ºo.]?\s*)?(\d{1,5}\.\d{3}/\d{2,4}|\d{1,5}/\d{2,4})", folded)
    if lei_num:
        return find_law(lei_num.group(1), docs)
    return None


def extract_article_block(body: str, numero: str) -> str | None:
    if not body:
        return None
    pat = re.compile(
        rf"(?m)^[ \t]*(Art\.?\s*{re.escape(str(numero))}(?:º|o)?\b.*?)(?=^[ \t]*Art\.?\s*\d|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pat.search(body)
    if not m:
        return None
    block = re.sub(r"[ \t]+\n", "\n", m.group(1)).strip()
    block = re.sub(r"\n{3,}", "\n\n", block)
    return block[:8000] if block else None


def extract_art_numbers(text: str) -> list[str]:
    seen: list[str] = []
    for m in ART_REF.finditer(text or ""):
        n = str(int(m.group(1)))
        if n not in seen:
            seen.append(n)
    return seen[:6]


_MATERIA_LAW = (
    ("processual penal", "decreto-lei 3.689/1941 — código de processo penal"),
    ("penal", "decreto-lei 2.848/1940 — código penal"),
    ("processual civil", "lei 13.105/2015 — código de processo civil"),
    ("civil", "lei 10.406/2002 — código civil"),
    ("constitucional", "constituição federal de 1988"),
    ("administrativ", "constituição federal de 1988"),
    ("tribut", "constituição federal de 1988"),
    ("humanos", "constituição federal de 1988"),
)


def law_from_materia(materia: str, docs: list[dict[str, Any]]) -> dict[str, Any] | None:
    folded = _fold(materia)
    for needle, title in _MATERIA_LAW:
        if needle in folded:
            return find_law(title, docs)
    return None


def lookup_dispositivos(text: str, materia: str = "") -> list[dict[str, str]]:
    docs, bodies = _legis_index()
    law = resolve_law(text, docs) or law_from_materia(materia, docs)
    if not law:
        return []
    body = bodies.get(_doc_key(law)) or ""
    out: list[dict[str, str]] = []
    for num in extract_art_numbers(text):
        bloco = extract_article_block(body, num)
        if not bloco:
            continue
        out.append({"lei": _title_of(law), "artigo": num, "texto": bloco, "url": str(law.get("url") or "")})
    return out


def lookup_jurisprudencia(text: str, *, limit: int = 3) -> list[dict[str, str]]:
    folded = _fold(text)
    hits: list[dict[str, str]] = []
    for m in SUMULA_REF.finditer(text or ""):
        numero = int(m.group(1))
        vinculante = "vinculante" in _fold(m.group(0))
        for s in _sumulas():
            try:
                n = int(s.get("numero"))
            except (TypeError, ValueError):
                continue
            if n != numero:
                continue
            if vinculante and not s.get("vinculante"):
                continue
            hits.append(
                {
                    "tribunal": str(s.get("tribunal") or ""),
                    "ref": str(s.get("title") or f"Súmula {numero}"),
                    "texto": str(s.get("enunciado") or s.get("preview") or "").strip(),
                    "url": str(s.get("url") or ""),
                }
            )
            break

    if hits:
        return hits[:limit]

    stop = {"sobre", "como", "para", "pela", "pelo", "uma", "com", "direito", "questao", "alternativa"}
    tokens = [t for t in re.findall(r"[a-z0-9]{5,}", folded) if t not in stop]
    scored: list[tuple[int, dict[str, Any]]] = []
    for s in _sumulas():
        blob = _fold(f"{s.get('title','')} {s.get('enunciado','')}")
        score = sum(1 for t in tokens if t in blob)
        if score >= 7:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    for _, s in scored[: limit - len(hits)]:
        hits.append(
            {
                "tribunal": str(s.get("tribunal") or ""),
                "ref": str(s.get("title") or ""),
                "texto": str(s.get("enunciado") or s.get("preview") or "").strip(),
                "url": str(s.get("url") or ""),
            }
        )
    return hits[:limit]
