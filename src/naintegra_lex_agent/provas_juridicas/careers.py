"""Carreiras-alvo da varredura: juiz, promotor, defensor e procurador de Estado."""

from __future__ import annotations

from typing import Any

PROVA_YEARS = (2024, 2025, 2026)

PROVA_CAREERS: dict[str, dict[str, Any]] = {
    "juiz": {
        "label": "Juiz",
        "carreiras": ("juiz_estadual", "juiz_federal"),
        "materias": (),
    },
    "promotor": {
        "label": "Promotor",
        "carreiras": ("juiz_estadual", "juridica", "procuradoria"),
        "materias": (
            "Direito Penal",
            "Direito Processual Penal",
            "Direito Constitucional",
            "Direito Administrativo",
            "Direitos Humanos",
        ),
    },
    "defensor": {
        "label": "Defensor",
        "carreiras": ("juridica", "procuradoria", "juiz_estadual"),
        "materias": (
            "Direito Penal",
            "Direito Processual Penal",
            "Direito Civil",
            "Direito Processual Civil",
            "Direito Constitucional",
            "Direitos Humanos",
        ),
    },
    "procurador": {
        "label": "Procurador de Estado",
        "carreiras": ("procuradoria", "agu"),
        "materias": (),
    },
}

ORIGEM_LABEL = {
    "juiz_estadual": "Magistratura estadual",
    "juiz_federal": "Magistratura federal",
    "procuradoria": "Procuradoria",
    "agu": "AGU / advocacia pública",
    "juridica": "Carreira jurídica",
}


def _norm(text: Any) -> str:
    return str(text or "").strip().lower()


def origem_carreira(row: dict[str, Any]) -> str:
    meta = row.get("meta") or {}
    org = row.get("organized") or {}
    raw = meta.get("carreira") or org.get("cargo") or ""
    return str(raw).strip().replace(" ", "_").lower()


def ano_int(row: dict[str, Any]) -> int | None:
    org = row.get("organized") or {}
    raw = org.get("ano") or (row.get("meta") or {}).get("ano")
    try:
        return int(str(raw).strip()[:4])
    except (TypeError, ValueError):
        return None


def materia_of(row: dict[str, Any]) -> str:
    org = row.get("organized") or {}
    return str(org.get("materia") or (row.get("meta") or {}).get("assunto") or "").strip()


def matches_career(row: dict[str, Any], career_id: str) -> bool:
    spec = PROVA_CAREERS[career_id]
    origem = origem_carreira(row)
    if origem not in spec["carreiras"]:
        return False
    allowed = spec["materias"]
    if not allowed:
        return True
    mat = materia_of(row)
    return any(_norm(mat) == _norm(m) for m in allowed)


def career_tags(row: dict[str, Any]) -> list[str]:
    return [cid for cid in PROVA_CAREERS if matches_career(row, cid)]


def in_year_window(row: dict[str, Any], years: tuple[int, ...] = PROVA_YEARS) -> bool:
    year = ano_int(row)
    return year is not None and year in years
