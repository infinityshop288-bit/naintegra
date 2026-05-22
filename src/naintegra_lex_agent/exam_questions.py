"""Extração de questões objetivas/discursivas e gabaritos a partir de registros do crawl."""

from __future__ import annotations

from typing import Any

from .schemas import DocType

# Enunciado da questão (evitar só "enunciado" antes da detecção — ver pick_questoes_body).
QUESTAO_ENUNCIADO_KEYS: tuple[str, ...] = (
    "enunciado_questao",
    "texto_questao",
    "questao_texto",
    "questao",
    "stem",
    "comando",
)

GABARITO_OBJETIVO_KEYS: tuple[str, ...] = (
    "gabarito",
    "resposta_correta",
    "alternativa_correta",
    "chave",
    "resposta_oficial_objetiva",
)

RESPOSTA_SUBJETIVA_KEYS: tuple[str, ...] = (
    "resposta_oficial",
    "gabarito_discursivo",
    "resposta_modelo",
    "padrao_resposta",
    "ponto_avaliacao",
    "espelho_correcao",
)

ALTERNATIVAS_FIELDS: tuple[str, ...] = ("alternativas", "opcoes", "choices", "itens")

# Campos cuja cópia textual já entra no body composto (pick_questoes_body) — paridade com súmulas/dispositivo.
QUESTAO_HOIST_KEYS: frozenset[str] = frozenset(
    [
        *QUESTAO_ENUNCIADO_KEYS,
        "enunciado",
        *ALTERNATIVAS_FIELDS,
        *GABARITO_OBJETIVO_KEYS,
        *RESPOSTA_SUBJETIVA_KEYS,
    ]
)


def _first_str(mapping: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for k in keys:
        v = mapping.get(k)
        if v is not None:
            s = str(v).strip()
            if s:
                return s
    return None


def _nested_dict(record: dict[str, Any]) -> dict[str, Any]:
    for nk in ("metadata", "meta"):
        n = record.get(nk)
        if isinstance(n, dict):
            return n
    return {}


def _nested_str(record: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    hit = _first_str(record, keys)
    if hit:
        return hit
    return _first_str(_nested_dict(record), keys)


def _pick_alternativas_raw(record: dict[str, Any]) -> Any | None:
    for k in ALTERNATIVAS_FIELDS:
        v = record.get(k)
        if v is not None:
            return v
    nested = _nested_dict(record)
    for k in ALTERNATIVAS_FIELDS:
        v = nested.get(k)
        if v is not None:
            return v
    return None


def format_alternativas(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, list):
        lines: list[str] = []
        for item in val:
            if isinstance(item, dict):
                letra = item.get("letra") or item.get("id") or item.get("opcao")
                txt = item.get("texto") or item.get("text") or item.get("conteudo")
                if letra is not None and txt is not None:
                    lines.append(f"{str(letra).strip()}) {str(txt).strip()}")
                elif txt is not None:
                    lines.append(str(txt).strip())
            elif isinstance(item, str) and item.strip():
                lines.append(item.strip())
        return "\n".join(lines) if lines else None
    if isinstance(val, dict):
        parts: list[str] = []
        for k in sorted(val.keys(), key=lambda x: str(x)):
            parts.append(f"{k}) {val[k]}")
        return "\n".join(parts) if parts else None
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


def pick_gabarito_objetivo(record: dict[str, Any]) -> str | None:
    h = _nested_str(record, GABARITO_OBJETIVO_KEYS)
    return h


def pick_resposta_subjetiva(record: dict[str, Any]) -> str | None:
    h = _nested_str(record, RESPOSTA_SUBJETIVA_KEYS)
    return h


def looks_like_questao(record: dict[str, Any]) -> bool:
    raw = str(record.get("type") or record.get("doc_type") or record.get("tipo") or "").lower()
    if any(
        x in raw
        for x in (
            "questoes_objetivas",
            "questoes_subjetivas",
            "questao_objetiva",
            "questao_subjetiva",
            "questao_discursiva",
            "prova_objetiva",
            "prova_discursiva",
        )
    ):
        return True
    if _pick_alternativas_raw(record) is not None:
        return True
    if pick_gabarito_objetivo(record) and (
        _nested_str(record, QUESTAO_ENUNCIADO_KEYS) or _nested_str(record, ("texto", "body"))
    ):
        return True
    if pick_resposta_subjetiva(record) and _nested_str(record, QUESTAO_ENUNCIADO_KEYS):
        return True
    nested = _nested_dict(record)
    if nested.get("banca") is not None and (
        nested.get("numero_questao") is not None or nested.get("questao_numero") is not None
    ):
        return True
    return False


def pick_questoes_body(record: dict[str, Any]) -> str | None:
    """Texto principal para Lex quando o registro é questão de banca."""

    if not looks_like_questao(record):
        return None

    enun = _nested_str(record, QUESTAO_ENUNCIADO_KEYS)
    if not enun:
        # Evita roubar enunciado de súmula; aqui já sabemos que é questão.
        e2 = _nested_str(record, ("enunciado",))
        if e2:
            enun = e2
    if not enun:
        for k in ("texto", "body", "content"):
            v = record.get(k)
            if v is not None and str(v).strip():
                enun = str(v).strip()
                break

    parts: list[str] = []
    if enun:
        parts.append(enun)

    alt_raw = _pick_alternativas_raw(record)
    alt_txt = format_alternativas(alt_raw)
    if alt_txt:
        parts.append("")
        parts.append(alt_txt)

    go = pick_gabarito_objetivo(record)
    rs = pick_resposta_subjetiva(record)
    if go:
        parts.append("")
        parts.append(f"Gabarito (objetiva): {go}")
    if rs:
        parts.append("")
        parts.append("Resposta de referência (discursiva):\n" + rs)

    if parts:
        return "\n".join(parts).strip()
    return None


def prime_meta_for_doc_inference(meta: dict[str, Any], clean: dict[str, Any]) -> dict[str, Any]:
    """Eleva gabarito/alternativas aninhados ao meta plano para infer_doc_type/heurísticas."""

    out = dict(meta)
    gab_o = pick_gabarito_objetivo(clean)
    gab_s = pick_resposta_subjetiva(clean)
    if gab_o and out.get("gabarito") is None:
        out["gabarito"] = gab_o
    if gab_s and out.get("resposta_oficial") is None:
        out["resposta_oficial"] = gab_s
    alt = _pick_alternativas_raw(clean)
    if alt is not None and out.get("alternativas") is None:
        out["alternativas"] = alt
    return out


def enrich_questoes_meta(
    meta: dict[str, Any],
    clean: dict[str, Any],
    doc_type: DocType | None,
) -> dict[str, Any]:
    """Normaliza gabaritos e metadados de prova no meta (preserva o que já veio do crawl)."""

    out = prime_meta_for_doc_inference(meta, clean)

    if doc_type not in (DocType.QUESTOES_OBJETIVAS, DocType.QUESTOES_SUBJETIVAS):
        return out

    fmt = out.get("formato_questao") or clean.get("formato_questao")
    if fmt is None:
        out["formato_questao"] = (
            "objetiva" if doc_type == DocType.QUESTOES_OBJETIVAS else "subjetiva"
        )

    return out
