"""Seleção do texto principal (dispositivo, enunciado, ementa) a partir de registros do crawl."""

from __future__ import annotations

from typing import Any

from .exam_questions import pick_questoes_body, QUESTAO_HOIST_KEYS

# Legislação — dispositivos normativos.
DISPOSITIVO_KEYS: tuple[str, ...] = (
    "dispositivo",
    "dispositivo_legal",
    "texto_dispositivo",
    "integra_dispositivo",
    "texto_normativo",
    "norma_juridica",
    "norma",
    "conteudo_normativo",
    "conteudo_artigo",
    "texto_artigo",
    "texto_do_artigo",
    "corpo_artigo",
    "artigo_texto",
    "texto_integral_dispositivo",
    "ementa_dispositivo",
)

# Súmulas — enunciado costuma vir separado de `texto` (resumo).
SUMULA_BODY_KEYS: tuple[str, ...] = (
    "enunciado",
    "texto_enunciado",
    "texto_sumula",
    "sumula_texto",
    "enunciado_sumula",
)

# Jurisprudência — ementa / decisão.
JURISPRUDENCIA_BODY_KEYS: tuple[str, ...] = (
    "ementa",
    "texto_ementa",
    "texto_acordao",
    "acordao_texto",
    "inteiro_teor",
    "texto_decisao",
    "decisao_texto",
    "fundamentacao",
)

# Comentário / didática para jurisprudência (fora do `body`).
EXPLICACAO_KEYS: tuple[str, ...] = (
    "explicacao",
    "explicação",
    "comentario_juris",
    "notas_explicativas",
    "explicacao_jurisprudencia",
    "explicacao_pedagogica",
)

ALL_HOIST_BODY_KEYS: frozenset[str] = (
    frozenset(DISPOSITIVO_KEYS)
    | frozenset(SUMULA_BODY_KEYS)
    | frozenset(JURISPRUDENCIA_BODY_KEYS)
    | QUESTAO_HOIST_KEYS
)

# Ao promover texto ao `body`, remove-se do meta só lei/súmula/questão estruturada; ementa permanece para inferência/chips.
_META_STRIP_AFTER_HOIST_KEYS: frozenset[str] = (
    frozenset(DISPOSITIVO_KEYS) | frozenset(SUMULA_BODY_KEYS) | QUESTAO_HOIST_KEYS
)

TITLE_KEYS: tuple[str, ...] = (
    "titulo",
    "title",
    "epigrafe",
    "nome_lei",
    "nome_norma",
)


def _first_non_empty_str(mapping: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for k in keys:
        v = mapping.get(k)
        if v is not None:
            s = str(v).strip()
            if s:
                return s
    return None


def pick_nested_keys(record: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for nested_key in ("metadata", "meta"):
        nested = record.get(nested_key)
        if isinstance(nested, dict):
            hit = _first_non_empty_str(nested, keys)
            if hit:
                return hit
    return None


def pick_dispositivo_from_nested(record: dict[str, Any]) -> str | None:
    return pick_nested_keys(record, DISPOSITIVO_KEYS)


def pick_dispositivo_flat(record: dict[str, Any]) -> str | None:
    return _first_non_empty_str(record, DISPOSITIVO_KEYS)


def pick_body_from_artigos(record: dict[str, Any]) -> str | None:
    arts = record.get("artigos") or record.get("articles") or record.get("artigos_texto")
    if not isinstance(arts, list) or not arts:
        return None
    parts: list[str] = []
    for a in arts:
        if isinstance(a, dict):
            num = a.get("numero") or a.get("num") or a.get("id") or a.get("artigo")
            txt = _first_non_empty_str(
                a,
                (
                    "texto",
                    "dispositivo",
                    "texto_dispositivo",
                    "conteudo",
                    "corpo",
                    "ementa",
                    "enunciado",
                ),
            )
            if not txt:
                continue
            label = str(num).strip() if num is not None else ""
            if label.lower().startswith("art"):
                parts.append(f"{label}\n{txt}")
            elif label:
                parts.append(f"Art. {label}\n{txt}")
            else:
                parts.append(txt)
        elif isinstance(a, str) and a.strip():
            parts.append(a.strip())
    if not parts:
        return None
    return "\n\n".join(parts)


def pick_verbatim_body(record: dict[str, Any]) -> str | None:
    """Texto principal para `body` / Lex: legislação → súmula → jurisprudência → genérico."""

    d = pick_dispositivo_flat(record)
    if d:
        return d
    d = pick_dispositivo_from_nested(record)
    if d:
        return d
    d = pick_body_from_artigos(record)
    if d:
        return d

    d = pick_questoes_body(record)
    if d:
        return d

    d = _first_non_empty_str(record, SUMULA_BODY_KEYS)
    if d:
        return d
    d = pick_nested_keys(record, SUMULA_BODY_KEYS)
    if d:
        return d

    d = _first_non_empty_str(record, JURISPRUDENCIA_BODY_KEYS)
    if d:
        return d
    d = pick_nested_keys(record, JURISPRUDENCIA_BODY_KEYS)
    if d:
        return d

    for k in ("texto", "body", "content", "texto_completo", "integra"):
        v = record.get(k)
        if v is not None:
            s = str(v).strip()
            if s:
                return s
    return None


def pick_display_title(record: dict[str, Any]) -> str | None:
    return _first_non_empty_str(record, TITLE_KEYS)


def pick_explicacao(record: dict[str, Any]) -> str | None:
    """Texto de apoio ao estudo (jurisprudência principalmente); não entra em `body`."""

    hit = _first_non_empty_str(record, EXPLICACAO_KEYS)
    if hit:
        return hit
    return pick_nested_keys(record, EXPLICACAO_KEYS)


def strip_dispositivo_keys_from_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """Remove do meta campos já espelhados no `body` (lei/súmula). Mantém ementa etc. no meta."""

    out = dict(meta)
    for k in _META_STRIP_AFTER_HOIST_KEYS:
        out.pop(k, None)
    return out
