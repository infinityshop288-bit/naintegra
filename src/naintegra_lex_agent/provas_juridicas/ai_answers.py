"""Elabora a resposta da IA com o gabarito da banca, o dispositivo integral e a jurisprudência."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from .codex_client import DEFAULT_MODEL, create_response

logger = logging.getLogger(__name__)

SYSTEM = """Tu és jurista brasileiro que elabora gabaritos de concursos de juiz, promotor, defensor e procurador.

Regras:
- Responde em português, técnico e objetivo.
- Usa SOMENTE o enunciado, o gabarito da banca e os textos legais/jurisprudenciais fornecidos.
- Não inventes número de artigo, súmula ou processo.
- Transcreve o dispositivo legal aplicável por inteiro (já vem no material).
- Se o material não trouxer jurisprudência, escreve que não há precedente no acervo para o comando.
- Saída em Markdown com estes cabeçalhos exatos:

### Resposta da IA
### Dispositivo legal aplicável
### Jurisprudência
### Fundamentação
"""


def _alts_block(alts: Any) -> str:
    if not alts:
        return "(questão discursiva — sem alternativas)"
    if isinstance(alts, list):
        lines = []
        for i, a in enumerate(alts):
            if isinstance(a, dict):
                lines.append(f"- ({a.get('key') or a.get('letra') or chr(65+i)}) {a.get('text') or a.get('texto') or ''}")
            else:
                lines.append(f"- {a}")
        return "\n".join(lines)
    if isinstance(alts, dict):
        return "\n".join(f"- ({k}) {v}" for k, v in alts.items())
    return str(alts)


def _disp_block(dispositivos: list[dict[str, str]]) -> str:
    if not dispositivos:
        return "(Nenhum dispositivo integral localizado no acervo Lex para este comando.)"
    parts = []
    for d in dispositivos:
        parts.append(f"{d.get('lei','')}, art. {d.get('artigo','')}\n\n{d.get('texto','')}")
    return "\n\n---\n\n".join(parts)


def _juris_block(items: list[dict[str, str]]) -> str:
    if not items:
        return "(Sem jurisprudência/súmula correspondente no acervo Lex.)"
    return "\n\n".join(f"**{j.get('ref') or j.get('tribunal')}** — {j.get('texto','')}" for j in items)


def grounded_answer(
    *,
    enunciado: str,
    alternativas: Any,
    gabarito_banca: str,
    resposta_banca: str,
    dispositivos: list[dict[str, str]],
    jurisprudencia: list[dict[str, str]],
    subjetiva: bool,
) -> str:
    """Elaboração ancorada no acervo — usada sempre, e como fallback se a IA falhar."""
    if subjetiva:
        tese = resposta_banca.strip() or "A banca exige desenvolvimento do problema jurídico do enunciado."
        abertura = f"A resposta deve desenvolver o seguinte eixo cobrado pela banca: {tese}"
    else:
        letra = (gabarito_banca or "").strip() or "—"
        abertura = (
            f"A banca gabaritou a alternativa **{letra}**. "
            f"{resposta_banca.strip() or 'A tese vencedora é a que reproduz o comando legal abaixo.'}"
        )
    disp = _disp_block(dispositivos)
    juris = _juris_block(jurisprudencia)
    alts = _alts_block(alternativas)
    return (
        f"### Resposta da IA\n\n{abertura}\n\n"
        f"### Dispositivo legal aplicável\n\n{disp}\n\n"
        f"### Jurisprudência\n\n{juris}\n\n"
        f"### Fundamentação\n\n"
        f"O comando da questão ({enunciado[:280].rstrip()}…) "
        f"{'não traz alternativas formais.' if subjetiva else f'oferece as hipóteses:\\n{alts}'}\n\n"
        "A solução correta é a que aplica o dispositivo transcrito na íntegra e, quando houver, "
        "a orientação pretoriana acima — sem extrapolar o que a banca e o acervo autorizam."
    )


def build_user_prompt(row: dict[str, Any]) -> str:
    meta = row.get("meta") or {}
    return (
        f"Carreira: {', '.join(row.get('carreiras_prova') or [])}\n"
        f"Disciplina: {(row.get('organized') or {}).get('materia') or ''}\n"
        f"Tipo: {row.get('doc_type')}\n"
        f"Gabarito da banca (letra ou espelho): {meta.get('gabarito_banca') or ''}\n"
        f"Comentário/espelho da banca:\n{meta.get('resposta_banca') or ''}\n\n"
        f"Enunciado:\n{row.get('body') or ''}\n\n"
        f"Alternativas:\n{_alts_block(meta.get('alternativas'))}\n\n"
        f"DISPOSITIVOS JÁ LOCALIZADOS (transcreva-os por inteiro):\n{_disp_block(meta.get('dispositivos') or [])}\n\n"
        f"JURISPRUDÊNCIA JÁ LOCALIZADA:\n{_juris_block(meta.get('jurisprudencia') or [])}\n"
    )


def call_codex(user_prompt: str, *, model: str | None = None) -> str:
    return create_response(
        input_text=user_prompt[:14000],
        instructions=SYSTEM,
        model=model or DEFAULT_MODEL,
        temperature=0.2,
    ).strip()


def finalize_answer(row: dict[str, Any], *, use_ai: bool, model: str | None = None) -> tuple[str, str]:
    meta = row.get("meta") or {}
    base = grounded_answer(
        enunciado=str(row.get("body") or ""),
        alternativas=meta.get("alternativas"),
        gabarito_banca=str(meta.get("gabarito_banca") or ""),
        resposta_banca=str(meta.get("resposta_banca") or ""),
        dispositivos=list(meta.get("dispositivos") or []),
        jurisprudencia=list(meta.get("jurisprudencia") or []),
        subjetiva=row.get("doc_type") == "questoes_subjetivas",
    )
    if not use_ai:
        return base, "acervo"
    try:
        text = call_codex(build_user_prompt(row), model=model)
        if text and "### Resposta da IA" in text:
            return text, "ia"
        if text:
            return f"### Resposta da IA\n\n{text}\n\n" + re.sub(r"^### Resposta da IA\n+", "", base), "ia"
    except Exception as exc:
        logger.warning("IA indisponível: %s", exc)
    return base, "acervo"


def parse_optional_json(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
