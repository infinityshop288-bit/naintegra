"""Interpretação de efeitos jurídicos (alteração/revogação) a partir de metadados LEXML/crawl."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ImpactKind(str, Enum):
    ALTER = "altera"
    REVOKE = "revoga"
    REDRACTION = "redacao"
    ADD = "adiciona"
    UNKNOWN = "desconhecido"


LAW_NUM_RE = re.compile(
    r"(?:lei|decreto(?:-lei)?|mp|medida\s+provis[oó]ria|emenda\s+constitucional|"
    r"lc|lei\s+complementar)\s*(?:n[ºo°.]?\s*)?"
    r"(\d{1,5}(?:\.\d{3})*(?:/\d{2,4})?)",
    re.I,
)

REVOKE_PATTERNS = (
    re.compile(r"\brevog(?:a|am|ar|ou|ado|ada|adas|ados)\b", re.I),
    re.compile(r"\brevog(?:a-se|am-se)\b", re.I),
    re.compile(r"\b(?:fica|ficam)\s+revogad", re.I),
    re.compile(r"\b(?:declar(?:a|ar)\s+)?(?:a\s+)?(?:inconstitucionalidade|nulidade)\b", re.I),
)

ALTER_PATTERNS = (
    re.compile(r"\b(?:altera|alteram|alterar|alterou|alterando)\b", re.I),
    re.compile(r"\b(?:dá|dao|dar)\s+(?:nova\s+)?reda(?:ç|c)[aã]o\b", re.I),
    re.compile(r"\b(?:modifica|modificam|modificar)\b", re.I),
    re.compile(r"\b(?:acrescenta|acrescentam|inclui|incluem)\b", re.I),
)


def normalize_law_number(raw: str) -> str:
    s = re.sub(r"[^\d/]", "", (raw or "").strip())
    if "/" in s:
        num, year = s.split("/", 1)
        num = num.replace(".", "")
        return f"{num}/{year}" if year else num
    return s.replace(".", "")


def extract_law_numbers(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in LAW_NUM_RE.finditer(text or ""):
        n = normalize_law_number(m.group(1))
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


@dataclass
class ImpactAction:
    kind: ImpactKind
    target_law_numbers: list[str] = field(default_factory=list)
    source_title: str = ""
    source_urn: str = ""
    source_url: str = ""
    notes: str = ""


@dataclass
class ImpactReport:
    actions: list[ImpactAction] = field(default_factory=list)
    source_title: str = ""
    source_urn: str = ""
    source_url: str = ""

    def affected_law_numbers(self) -> set[str]:
        nums: set[str] = set()
        for act in self.actions:
            nums.update(act.target_law_numbers)
        return nums

    def has_revocation(self) -> bool:
        return any(a.kind == ImpactKind.REVOKE for a in self.actions)


def classify_impact_kind(text: str) -> ImpactKind:
    blob = text or ""
    if any(p.search(blob) for p in REVOKE_PATTERNS):
        return ImpactKind.REVOKE
    if any(p.search(blob) for p in ALTER_PATTERNS):
        return ImpactKind.ALTER
    if re.search(r"\b(?:institui|dispõe|regulamenta|cria)\b", blob, re.I):
        return ImpactKind.ADD
    return ImpactKind.UNKNOWN


def analyze_impact(
    *,
    title: str = "",
    ementa: str = "",
    urn: str = "",
    url: str = "",
) -> ImpactReport:
    blob = f"{title}\n{ementa}".strip()
    kind = classify_impact_kind(blob)
    targets = extract_law_numbers(blob)

    # Ementas do tipo "Altera a Lei nº 8.666" — alvo explícito
    alter_match = re.search(
        r"(?:altera|revoga|modifica|dá\s+nova\s+redação\s+(?:ao|à|dos|das))\s+"
        r"(?:a\s+)?(?:lei|decreto|mp|lc)\s*(?:n[ºo°.]?\s*)?(\d[\d./]*)",
        blob,
        re.I,
    )
    if alter_match:
        n = normalize_law_number(alter_match.group(1))
        if n and n not in targets:
            targets.insert(0, n)

    actions: list[ImpactAction] = []
    if kind != ImpactKind.UNKNOWN or targets:
        actions.append(
            ImpactAction(
                kind=kind,
                target_law_numbers=targets,
                source_title=title,
                source_urn=urn,
                source_url=url,
            )
        )
    return ImpactReport(actions=actions, source_title=title, source_urn=urn, source_url=url)


def law_number_in_url(url: str) -> str | None:
    u = url or ""
    m = re.search(r"l(\d{4,5})(?:cons|compilad|consolidad)?", u, re.I)
    if m:
        return m.group(1)
    m = re.search(r"/(\d{4,5})\.htm", u, re.I)
    if m:
        return m.group(1)
    return None


def catalog_urls_for_law_numbers(
    catalog: list[dict[str, str]],
    law_numbers: set[str],
) -> list[dict[str, str]]:
    """Retorna entradas do catálogo cujo número coincide com os alvos."""
    if not law_numbers:
        return []
    normalized_targets = {normalize_law_number(n) for n in law_numbers}
    out: list[dict[str, str]] = []
    for item in catalog:
        url = str(item.get("url") or "")
        num = law_number_in_url(url)
        if num and num in normalized_targets:
            out.append(item)
            continue
        title_nums = extract_law_numbers(str(item.get("titulo") or ""))
        if any(normalize_law_number(n) in normalized_targets for n in title_nums):
            out.append(item)
    return out


def should_remove_entire_law(*, title: str, body: str, min_revoked_ratio: float = 0.72) -> bool:
    """Heurística: norma inteira revogada (texto quase todo ~~ ou título indica revogação total)."""
    t = (title or "").lower()
    if re.search(r"\brevogad[oa]\b|\brevogada\b|\bsem\s+efeito\b", t):
        return True
    text = body or ""
    if not text.strip():
        return True
    if re.search(r"^#?\s*revogad", text.strip()[:120], re.I | re.M):
        return True
    # Contagem de trechos revogados (formato Lex ~~...~~)
    parts = re.split(r"~~", text)
    if len(parts) < 3:
        return False
    revoked_chars = sum(len(p) for i, p in enumerate(parts) if i % 2 == 1)
    total = len(re.sub(r"~~", "", text))
    if total < 100:
        return False
    return (revoked_chars / total) >= min_revoked_ratio


def crawl_record_from_hit(
    hit: dict[str, Any],
    report: ImpactReport,
) -> dict[str, Any]:
    """Formato JSONL compatível com naintegra-crawl / agent ingest."""
    urn = str(hit.get("urn") or report.source_urn or "")
    url = str(hit.get("url") or hit.get("planalto_url") or report.source_url or "")
    title = str(hit.get("title") or hit.get("titulo") or report.source_title or urn)
    ementa = str(hit.get("ementa") or hit.get("description") or "")
    ext_id = f"lexml::{urn}" if urn else f"lexml::planalto::{url}"
    targets = sorted(report.affected_law_numbers())
    return {
        "external_id": ext_id,
        "id": ext_id,
        "doc_type": "legislacao",
        "type": "legislacao",
        "source": "lexml",
        "source_system": "lexml",
        "titulo": title,
        "title": title,
        "url": url,
        "urn": urn,
        "ementa": ementa,
        "metadata": {
            "autoridade": hit.get("autoridade") or "Federal",
            "tipo_documento": hit.get("tipo") or "Legislação",
            "data": hit.get("date"),
            "impacto": [a.kind.value for a in report.actions],
            "leis_alvo": targets,
            "corpus": "legislacao_lexml_weekly",
        },
    }
