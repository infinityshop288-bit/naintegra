"""Geração de conteúdo Instagram — Ollama padrão; multi-provedor para comparação."""

from __future__ import annotations

from typing import Any

from naintegra_meta.ai_providers import (
    ProviderId,
    complete_text,
    parse_json_array,
    resolve_provider_settings,
)
from naintegra_meta.settings import MetaSettings
from naintegra_meta.marketing_library import build_marketing_context
from naintegra_meta.zamboni_style import EXPOSURE_RULES, SYSTEM_PROMPT_ZAMBONI

HASHTAGS = [
    "#direitopenal",
    "#concursopolicial",
    "#delegado",
    "#oab",
    "#naintegra",
    "#estudecomquemvive",
    "#direitoprocessualpenal",
]


def _fallback_zamboni(tema: str, formato: str, slot: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    macro = (slot or {}).get("tema_macro") or tema
    gancho = "Indo DIRETO ao ponto — o que a banca adora confundir."
    legenda = (
        f"1) Tema: {macro}\n\n"
        "2) Na prática de concurso, o erro é tratar exceção como regra — "
        "revise o dispositivo e a jurisprudência dominante.\n\n"
        "3) Como professor e Delegado de Polícia Federal, trago o recorte "
        "que separa quem passa de quem trava na hora H.\n\n"
        "Qual a sua opinião? Escreve nos comentários!\n\n"
        "Conteúdo educacional. Não representa posição institucional.\n\n"
        "Comente MATERIAL para receber o PDF NaIntegra no inbox."
    )
    return [
        {
            "titulo": macro[:120],
            "gancho": gancho,
            "texto_overlay": "[EXPLICAÇÃO NA LEGENDA]",
            "roteiro_falas": (
                f"Olá! Hoje, direto ao ponto: {macro}. "
                "Abra a legenda — deixei a análise numerada. Comente MATERIAL."
            ),
            "legenda": legenda,
            "hashtags": HASHTAGS,
            "cta": "Comente MATERIAL — link NaIntegra na bio.",
            "formato_sugerido": formato,
            "slides": (
                [
                    f"1/6 — {macro}",
                    "2/6 — Fato hipotético (prova)",
                    "3/6 — Tipificação",
                    "4/6 — Pegadinha",
                    "5/6 — Jurisprudência (revisar edital)",
                    "6/6 — CTA MATERIAL",
                ]
                if formato == "carrossel"
                else []
            ),
        }
    ]


def generate_content_ideas(
    tema: str,
    formato: str,
    *,
    settings: MetaSettings | None = None,
    provider: ProviderId | None = None,
    contexto_lex: str | None = None,
    slot: dict[str, Any] | None = None,
    count: int = 3,
) -> tuple[list[dict[str, Any]], str]:
    """Retorna (ideias, fonte) onde fonte é provider|fallback."""

    del settings  # credenciais via resolve_provider_settings / env
    cfg = resolve_provider_settings()
    pid: ProviderId = provider or cfg["provider"]  # type: ignore[assignment]

    user_prompt = (
        f"Tema do dia: {tema}\n"
        f"Formato: {formato}\n"
        f"Quantidade: {count} ideia(s) no array JSON.\n"
    )
    if slot:
        user_prompt += f"Slot editorial: {slot.get('slot_id')} — {slot.get('tema_macro')}\n"
    if contexto_lex:
        user_prompt += f"\n--- CONTEXTO LEX (use como base factual) ---\n{contexto_lex[:8000]}\n"
    user_prompt += f"\n--- MARKETING DIGITAL ---\n{build_marketing_context(4000)}\n"

    system = SYSTEM_PROMPT_ZAMBONI.replace("array de 1 objeto", f"array de {count} objeto(s)")

    try:
        raw, used, model = complete_text(system=system, user_prompt=user_prompt, provider=pid, cfg=cfg)
        ideas = parse_json_array(raw)
        if not ideas:
            raise RuntimeError("Lista vazia")
        source = f"{used}:{model}"
        return ideas[:count], source
    except Exception:
        return _fallback_zamboni(tema, formato, slot)[:count], "fallback"


def generate_post_for_slot(
    slot: dict[str, Any],
    *,
    provider: ProviderId | None = None,
) -> tuple[dict[str, Any], str]:
    """Pacote completo (texto + imagens) para fila de aprovação."""

    from naintegra_meta.content_package import generate_content_package

    tema = str(slot.get("tema_macro") or "Concurso policial")
    fmt = str(slot.get("formato") or "reels")
    item = generate_content_package(
        tema=tema,
        formato=fmt,
        text_provider=provider,
        discipline=slot.get("discipline") if isinstance(slot.get("discipline"), str) else None,
    )
    item.setdefault("meta", {})["slot_id"] = slot.get("slot_id")
    item["meta"]["calendar_date"] = slot.get("date")
    return item, str(item.get("text_source") or "package")
