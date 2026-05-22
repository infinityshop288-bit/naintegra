"""Formatação opcional de texto jurídico via Ollama (API OpenAI-compatible)."""

from __future__ import annotations

import logging
import re
from typing import Any

from .ai_organizer import _openai_compatible_chat, default_ai_model
from .settings import Settings

logger = logging.getLogger(__name__)

_FORMAT_SYSTEM = """Você formata material jurídico brasileiro para estudo de concursos públicos.
Reformate o texto de entrada SEM inventar ou alterar o conteúdo jurídico.
Remova menus, links markdown, propagandas, rodapés de site e lixo de navegação.

Legislação: epígrafe/título, ementa (se existir), artigos e parágrafos numerados.
Jurisprudência ou súmula: blocos claros — Ementa, Tese (se houver), Julgado ou Enunciado.
Preserve literalmente dispositivos legais e enunciados oficiais.

Responda APENAS com o texto formatado em português, sem JSON e sem comentários meta."""


def needs_ai_format(body: str) -> bool:
    if not body or len(body.strip()) < 80:
        return False
    low = body.lower()
    if "\ufffd" in body or "Ã" in body:
        return True
    if low.count("[") >= 4 or low.count("http") >= 3:
        return True
    noise = (
        "trilhante",
        "buscador",
        "aprenda",
        "entrar",
        "cadastre-se",
        "menu principal",
        "compartilhar no",
    )
    if any(n in low for n in noise):
        return True
    if re.search(r"\]\(https?://", body):
        return True
    return False


def format_body_with_ollama(
    settings: Settings,
    *,
    body: str,
    doc_type: str,
    title: str | None = None,
) -> str | None:
    base = settings.resolved_openai_compatible_base_url()
    if not base and settings.norma_ai_format_enabled:
        base = "http://127.0.0.1:11434/v1"
    if not base:
        logger.warning("Formatação Ollama: base URL não configurada")
        return None
    model = (settings.ai_model or "").strip() or default_ai_model("ollama")
    key = (settings.openai_compatible_api_key or "").strip() or None
    hint = f"Tipo: {doc_type}."
    if title:
        hint += f" Título: {title}."
    user = f"{hint}\n\n--- TEXTO ---\n{body[: int(settings.ai_max_input_chars)]}"
    try:
        out = _openai_compatible_chat(
            base_url=base,
            api_key=key,
            model=model,
            system=_FORMAT_SYSTEM,
            user_prompt=user,
            timeout=float(settings.ai_timeout_seconds),
            temperature=0.1,
        )
    except Exception:
        logger.exception("Falha ao formatar texto com Ollama")
        return None
    cleaned = (out or "").strip()
    if len(cleaned) < max(40, len(body.strip()) // 4):
        logger.warning("Ollama retornou texto curto demais; mantendo original")
        return None
    return cleaned


def maybe_format_body(
    settings: Settings,
    body: str,
    *,
    doc_type: str,
    title: str | None,
) -> str:
    if not settings.norma_ai_format_enabled and settings.norma_ai_format_mode == "off":
        return body
    mode = settings.norma_ai_format_mode
    if mode == "off" and settings.norma_ai_format_enabled:
        mode = "fallback"
    if mode == "fallback" and not needs_ai_format(body):
        return body
    formatted = format_body_with_ollama(settings, body=body, doc_type=doc_type, title=title)
    return formatted if formatted else body
