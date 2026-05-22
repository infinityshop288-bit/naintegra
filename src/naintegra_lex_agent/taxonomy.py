from __future__ import annotations

import re
from typing import Any

# Tribunal: valores canônicos para UI NaIntegra Lex (briefing §3.3)
TRIBUNAL_ALIASES: dict[str, str] = {
    "stf": "STF",
    "supremo": "STF",
    "supremo tribunal federal": "STF",
    "stj": "STJ",
    "superior tribunal de justica": "STJ",
    "tst": "TST",
    "tribunal superior do trabalho": "TST",
    "tse": "TSE",
    "tribunal superior eleitoral": "TSE",
    "stm": "STM",
    "tribunal militar": "STM",
}

MATERIA_ALIASES: dict[str, str] = {
    "penal": "Penal",
    "direito penal": "Penal",
    "administrativo": "Administrativo",
    "adm": "Administrativo",
    "processual": "Processual",
    "processo": "Processual",
    "tributario": "Tributário",
    "tributário": "Tributário",
    "constitucional": "Constitucional",
    "civil": "Civil",
    "trabalho": "Trabalho",
    "trabalhista": "Trabalho",
    "eleitoral": "Eleitoral",
}

# Bancas e instituições examinadoras (concursos).
BANCA_ALIASES: dict[str, str] = {
    "cespe": "CESPE",
    "cebrap": "CEBRAP",
    "cebraspe": "CEBRASPE",
    "fcc": "FCC",
    "fgv": "FGV",
    "fundacao getulio vargas": "FGV",
    "vunesp": "VUNESP",
    "ibfc": "IBFC",
    "funcern": "FUNCERN",
    "aocep": "AOCEP",
    "quadrix": "QUADRIX",
    "cs": "CS-UFG",
}


def _norm_key(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def canonical_tribunal(value: str | None) -> str | None:
    if not value:
        return None
    key = _norm_key(value)
    return TRIBUNAL_ALIASES.get(key, value.strip().upper())


def canonical_materia(value: str | None) -> str | None:
    if not value:
        return None
    key = _norm_key(value)
    return MATERIA_ALIASES.get(key, value.strip().title())


def canonical_banca(value: str | None) -> str | None:
    if not value:
        return None
    key = _norm_key(value)
    return BANCA_ALIASES.get(key, value.strip().upper())


def infer_doc_type(raw_type: str | None, meta: dict[str, Any]) -> str | None:
    if raw_type:
        t = _norm_key(raw_type)
        if "questoes_objetivas" in t or "questao_objetiva" in t or t in ("mcq", "multipla_escolha"):
            return "questoes_objetivas"
        if (
            "questoes_subjetivas" in t
            or "questao_subjetiva" in t
            or "discursiva" in t
            or "dissertativa" in t
        ):
            return "questoes_subjetivas"
        if "sumula" in t or "súmula" in raw_type.lower():
            return "sumula"
        if "juris" in t or "acord" in t or "decis" in t:
            return "jurisprudencia"
        if "lei" in t or "legis" in t or "norma" in t or "ato" in t:
            return "legislacao"
    fmt_raw = meta.get("formato_questao") or meta.get("tipo_questao")
    if fmt_raw:
        fk = _norm_key(str(fmt_raw))
        if fk in ("objetiva", "multipla_escolha", "mcq", "certo_errado", "multipla escolha"):
            return "questoes_objetivas"
        if fk in ("subjetiva", "discursiva", "dissertativa"):
            return "questoes_subjetivas"

    if meta.get("alternativas") is not None or meta.get("opcoes") is not None:
        if meta.get("gabarito") or meta.get("resposta_correta"):
            return "questoes_objetivas"

    if (
        meta.get("resposta_oficial")
        or meta.get("gabarito_discursivo")
        or meta.get("resposta_modelo")
    ) and meta.get("alternativas") is None and meta.get("opcoes") is None:
        return "questoes_subjetivas"

    # fallback por campos
    if meta.get("sumula_numero") or meta.get("numero_sumula"):
        return "sumula"
    if meta.get("tribunal") and meta.get("ementa"):
        return "jurisprudencia"
    return None


def organize_fields(meta: dict[str, Any]) -> dict[str, Any]:
    """Campos derivados para consumo no front (lex / naintegracursos)."""

    tribunal = canonical_tribunal(
        meta.get("tribunal") or meta.get("court") or meta.get("orgao")
    )
    materia = canonical_materia(meta.get("materia") or meta.get("assunto") or meta.get("area"))
    banca = canonical_banca(meta.get("banca") or meta.get("orgao_examinador") or meta.get("instituicao"))

    secao_lei_seca: str | None = None
    if meta.get("secao_lei_seca"):
        secao_lei_seca = str(meta["secao_lei_seca"])
    elif meta.get("categoria_lei"):
        secao_lei_seca = str(meta["categoria_lei"])

    fmt_q = meta.get("formato_questao")
    formato_questao: str | None = None
    if fmt_q is not None and str(fmt_q).strip():
        formato_questao = str(fmt_q).strip().title()

    ano_val = meta.get("ano") or meta.get("ano_prova")
    ano: int | None = None
    if ano_val is not None:
        try:
            ano = int(ano_val)
        except (TypeError, ValueError):
            ano = None

    cargo = meta.get("cargo") or meta.get("cargo_prova")
    cargo_str = str(cargo).strip() if cargo not in (None, "") else None

    nq = meta.get("numero_questao") or meta.get("questao_numero")
    numero_questao: str | None = None
    if nq is not None:
        numero_questao = str(nq).strip()

    out: dict[str, Any] = {
        "tribunal": tribunal,
        "materia": materia,
        "banca": banca,
        "ano": ano,
        "cargo": cargo_str,
        "numero_questao": numero_questao,
        "formato_questao": formato_questao,
        "secao_lei_seca": secao_lei_seca,
        "lex_ml_urn": meta.get("urn") or meta.get("lexml_urn"),
        "numeracao": meta.get("numeracao") or meta.get("numero") or meta.get("id_publico"),
        "vinculante": bool(meta.get("vinculante")) if meta.get("vinculante") is not None else None,
        "tags_incidencia": meta.get("tags_incidencia") or meta.get("bancas"),
    }
    return {k: v for k, v in out.items() if v is not None}
