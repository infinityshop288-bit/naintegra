"""Elabora resumos de estudo via Responses API, sem inventar lei ou julgado."""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

from naintegra_lex_agent.provas_juridicas.codex_client import DEFAULT_MODEL, create_response

SYSTEM = """Tu és jurista brasileiro que atualiza material de estudo do NaIntegra Lex.

Regras:
- Usa SOMENTE o texto oficial ou doutrinário fornecido.
- Não inventes artigo, súmula, tema, processo, ementa ou alteração legislativa.
- Se o texto for insuficiente, declara isso no resumo.
- Responde APENAS um JSON válido, sem markdown.
"""


def strip_html(raw: str) -> str:
    text = unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    return re.sub(r"\s+", " ", text).strip()


def parse_json_object(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def ask_json(prompt: str, *, model: str | None = None) -> dict[str, Any]:
    raw = create_response(
        input_text=prompt[:14000],
        instructions=SYSTEM,
        model=model or DEFAULT_MODEL,
        temperature=0.15,
    )
    data = parse_json_object(raw)
    if data:
        return data
    text = (raw or "").strip()
    if len(text) >= 40:
        return {"resumo": text[:900], "tese": text[:900], "titulo": "", "secao": "", "aplicacao": "", "legal_refs": [], "dicas": []}
    raise RuntimeError("IA não devolveu JSON")


def resumo_legislacao(*, titulo: str, secao: str, texto: str, model: str | None = None) -> dict[str, Any]:
    data = ask_json(
        (
            "Atualize o resumo de estudo desta lei. JSON: "
            '{"titulo":"...","resumo":"2 a 4 frases","secao":"..."}\n\n'
            f"Título: {titulo}\nSeção: {secao}\n\nTEXTO OFICIAL:\n{texto[:9000]}"
        ),
        model=model,
    )
    return {
        "titulo": str(data.get("titulo") or titulo).strip() or titulo,
        "resumo": str(data.get("resumo") or "").strip(),
        "secao": str(data.get("secao") or secao).strip() or secao,
    }


def resumo_jurisprudencia(*, titulo: str, enunciado: str, model: str | None = None) -> dict[str, Any]:
    data = ask_json(
        (
            "Elabore tese de estudo a partir do enunciado oficial. JSON: "
            '{"tese":"...","aplicacao":"1 ou 2 frases"}\n\n'
            f"Título: {titulo}\n\nENUNCIADO OFICIAL:\n{enunciado[:6000]}"
        ),
        model=model,
    )
    return {
        "tese": str(data.get("tese") or "").strip(),
        "aplicacao": str(data.get("aplicacao") or "").strip(),
    }


def resumo_doutrina(*, titulo: str, corpo: str, model: str | None = None) -> dict[str, Any]:
    data = ask_json(
        (
            "Atualize o resumo doutrinário. JSON: "
            '{"resumo":"...","legal_refs":["só as que estiverem no texto"],"dicas":["..."]}\n\n'
            f"Título: {titulo}\n\nTEXTO:\n{corpo[:8000]}"
        ),
        model=model,
    )
    refs = data.get("legal_refs") or []
    dicas = data.get("dicas") or []
    return {
        "resumo": str(data.get("resumo") or "").strip(),
        "legal_refs": [str(x) for x in refs if str(x).strip()][:8],
        "dicas": [str(x) for x in dicas if str(x).strip()][:6],
    }
