"""Geração de ideias de conteúdo via Claude, com fallback local."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from naintegra_meta.settings import MetaSettings

SYSTEM_PROMPT = """Você é estrategista de conteúdo para @delegadoluizcarlos — Delegado de Polícia Federal
que ensina Direito Penal e preparação para concursos policiais/OAB. Diferencial: autoridade real +
casos práticos (flagrante, IPL, tipificação, dolo eventual). Objetivo: gerar leads para NaIntegra Cursos.

Responda SOMENTE com JSON válido (array de 3 objetos), sem markdown:
[
  {
    "titulo": "...",
    "gancho": "...",
    "legenda": "...",
    "hashtags": ["#..."],
    "cta": "...",
    "formato_sugerido": "carrossel|reels|story"
  }
]"""

HASHTAGS = [
    "#direitopenal",
    "#concursopolicial",
    "#delegado",
    "#oab",
    "#naintegra",
    "#estudecomquemvive",
]


def _fallback_ideas(tema: str, formato: str) -> list[dict[str, Any]]:
    templates = [
        {
            "titulo": f"Erro clássico em {tema}",
            "gancho": "90% dos candidatos confundem isso na prova — e na vida real também.",
            "legenda": (
                f"Você sabia que {tema} é um dos temas mais cobrados?\n\n"
                "Como Delegado de Polícia Federal, vejo na prática onde a teoria engana.\n"
                "Salve este post e compartilhe com quem está estudando para concurso."
            ),
        },
        {
            "titulo": f"Caso prático: {tema}",
            "gancho": "Do flagrante ao IPL — o que muda na tipificação?",
            "legenda": (
                f"Hoje vamos destrinchar {tema} com um exemplo real de atuação policial.\n\n"
                "1) Fato\n2) Tipificação\n3) Pegadinha de prova\n\n"
                "Comenta “QUERO” que mando o material completo."
            ),
        },
        {
            "titulo": f"Checklist rápido — {tema}",
            "gancho": "3 pontos que separam quem passa de quem trava na hora H.",
            "legenda": (
                f"Checklist de {tema} para concurseiros:\n\n"
                "✓ Conceito-chave\n✓ Jurisprudência recente\n✓ Aplicação em questão\n\n"
                "Link na bio para o curso NaIntegra."
            ),
        },
    ]
    ideas: list[dict[str, Any]] = []
    for tpl in templates:
        ideas.append(
            {
                **tpl,
                "hashtags": HASHTAGS[:5],
                "cta": "Quer ir além? Acesse os cursos NaIntegra — link na bio.",
                "formato_sugerido": formato,
            }
        )
    return ideas


def generate_content_ideas(
    tema: str,
    formato: str,
    *,
    settings: MetaSettings | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Retorna (ideias, fonte) onde fonte é claude|fallback."""
    cfg = settings or MetaSettings()
    if not cfg.anthropic_api_key:
        return _fallback_ideas(tema, formato), "fallback"

    user_prompt = (
        f"Tema: {tema}\n"
        f"Formato preferido: {formato}\n"
        "Gere 3 ideias originais, práticas e com gancho forte para o nicho de concursos policiais."
    )
    payload = {
        "model": cfg.anthropic_model,
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "x-api-key": cfg.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
    if resp.status_code >= 400:
        body = resp.text[:500]
        if "credit balance" in body.lower() or resp.status_code in (402, 429):
            return _fallback_ideas(tema, formato), "fallback"
        raise RuntimeError(f"Claude API: {body}")

    data = resp.json()
    blocks = data.get("content") or []
    text = ""
    for block in blocks:
        if block.get("type") == "text":
            text += block.get("text", "")

    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise RuntimeError("Resposta da IA não é uma lista")
    return parsed, "claude"
