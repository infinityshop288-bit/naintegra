"""Provedores de IA para conteúdo Instagram — Ollama padrão; demais para comparação."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from naintegra_lex_agent.ai_organizer import (
    OLLAMA_DEFAULT_OPENAI_API_BASE,
    _openai_compatible_chat,
    _strip_json_fence,
)

ProviderId = Literal[
    "ollama",
    "anthropic",
    "openai",
    "openai_compatible",
    "gemini",
    "grok",
    "groq",
    "openrouter",
]

ALL_PROVIDERS: tuple[ProviderId, ...] = (
    "ollama",
    "anthropic",
    "openai",
    "gemini",
    "grok",
    "groq",
    "openrouter",
    "openai_compatible",
)


@dataclass(frozen=True)
class ProviderConfig:
    id: ProviderId
    label: str
    configured: bool
    model_default: str
    model_current: str
    detail: str


def _first_env(*names: str) -> str:
    for name in names:
        val = os.environ.get(name, "").strip()
        if val:
            return val
    return ""


def resolve_provider_settings() -> dict[str, Any]:
    """Lê DELEGADO_* com fallback para LEX_AGENT_* / ANTHROPIC_API_KEY / chaves globais."""

    provider = (
        _first_env("DELEGADO_AI_PROVIDER", "LEX_AGENT_AI_PROVIDER") or "ollama"
    ).strip().lower()
    if provider not in ALL_PROVIDERS:
        provider = "ollama"

    return {
        "provider": provider,
        "anthropic_api_key": _first_env(
            "DELEGADO_ANTHROPIC_API_KEY",
            "ANTHROPIC_API_KEY",
            "LEX_AGENT_ANTHROPIC_API_KEY",
            "QC_STUDY_ANTHROPIC_API_KEY",
        ),
        "openai_api_key": _first_env(
            "DELEGADO_OPENAI_API_KEY",
            "OPENAI_API_KEY",
            "LEX_AGENT_OPENAI_API_KEY",
            "QC_STUDY_OPENAI_API_KEY",
        ),
        "gemini_api_key": _first_env(
            "DELEGADO_GEMINI_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "GOOGLE_GENERATIVE_AI_API_KEY",
        ),
        "grok_api_key": _first_env(
            "DELEGADO_GROK_API_KEY",
            "GROK_API_KEY",
            "XAI_API_KEY",
        ),
        "groq_api_key": _first_env("DELEGADO_GROQ_API_KEY", "GROQ_API_KEY"),
        "openrouter_api_key": _first_env("DELEGADO_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
        "github_token": _first_env("DELEGADO_GITHUB_TOKEN", "GITHUB_TOKEN"),
        "openai_compatible_base_url": _first_env(
            "DELEGADO_OPENAI_COMPATIBLE_BASE_URL",
            "LEX_AGENT_OPENAI_COMPATIBLE_BASE_URL",
            "QC_STUDY_OPENAI_COMPATIBLE_BASE_URL",
        ),
        "openai_compatible_api_key": _first_env(
            "DELEGADO_OPENAI_COMPATIBLE_API_KEY",
            "LEX_AGENT_OPENAI_COMPATIBLE_API_KEY",
            "QC_STUDY_OPENAI_COMPATIBLE_API_KEY",
        ),
        "model": _first_env("DELEGADO_AI_MODEL", "LEX_AGENT_AI_MODEL", "QC_STUDY_AI_MODEL"),
        "timeout": float(
            _first_env("DELEGADO_AI_TIMEOUT_SECONDS", "LEX_AGENT_AI_TIMEOUT_SECONDS") or "120"
        ),
        "anthropic_model": _first_env("DELEGADO_ANTHROPIC_MODEL", "ANTHROPIC_MODEL")
        or "claude-sonnet-4-20250514",
        "openai_model": _first_env("DELEGADO_OPENAI_MODEL") or "gpt-4o-mini",
        "gemini_model": _first_env("DELEGADO_GEMINI_MODEL") or "gemini-2.0-flash",
        "grok_model": _first_env("DELEGADO_GROK_MODEL") or "grok-2-latest",
        "groq_model": _first_env("DELEGADO_GROQ_MODEL") or "llama-3.3-70b-versatile",
        "openrouter_model": _first_env("DELEGADO_OPENROUTER_MODEL")
        or "google/gemini-2.0-flash-exp:free",
        "ollama_model": _first_env("DELEGADO_OLLAMA_MODEL") or "llama3.2:3b",
    }


def default_model(provider: ProviderId, cfg: dict[str, Any]) -> str:
    custom = (cfg.get("model") or "").strip()
    if custom:
        return custom
    defaults: dict[ProviderId, str] = {
        "ollama": cfg["ollama_model"],
        "anthropic": cfg["anthropic_model"],
        "openai": cfg["openai_model"],
        "gemini": cfg["gemini_model"],
        "grok": cfg["grok_model"],
        "groq": cfg["groq_model"],
        "openrouter": cfg["openrouter_model"],
        "openai_compatible": cfg["ollama_model"],
    }
    return defaults.get(provider, cfg["ollama_model"])


def provider_configured(provider: ProviderId, cfg: dict[str, Any]) -> tuple[bool, str]:
    if provider == "ollama":
        return True, "Ollama local (http://127.0.0.1:11434)"
    if provider == "anthropic":
        key = cfg["anthropic_api_key"]
        return bool(key), "ANTHROPIC / DELEGADO_ANTHROPIC / LEX_AGENT_ANTHROPIC"
    if provider == "openai":
        key = cfg["openai_api_key"]
        return bool(key), "OPENAI / DELEGADO_OPENAI / LEX_AGENT_OPENAI"
    if provider == "gemini":
        key = cfg["gemini_api_key"]
        return bool(key), "GEMINI / GOOGLE_API_KEY / DELEGADO_GEMINI"
    if provider == "grok":
        key = cfg["grok_api_key"]
        return bool(key), "XAI / GROK / DELEGADO_GROK"
    if provider == "groq":
        key = cfg["groq_api_key"]
        return bool(key), "GROQ_API_KEY"
    if provider == "openrouter":
        key = cfg["openrouter_api_key"]
        return bool(key), "OPENROUTER_API_KEY"
    if provider == "openai_compatible":
        base = cfg["openai_compatible_base_url"] or OLLAMA_DEFAULT_OPENAI_API_BASE
        return bool(base), f"Base URL: {base}"
    return False, "desconhecido"


def list_provider_statuses(active: ProviderId | None = None) -> list[ProviderConfig]:
    cfg = resolve_provider_settings()
    active = active or cfg["provider"]  # type: ignore[assignment]
    labels: dict[ProviderId, str] = {
        "ollama": "Ollama (local)",
        "anthropic": "Claude (Anthropic)",
        "openai": "OpenAI",
        "gemini": "Gemini (Google)",
        "grok": "Grok (xAI)",
        "groq": "Groq",
        "openrouter": "OpenRouter",
        "openai_compatible": "OpenAI-compatible",
    }
    out: list[ProviderConfig] = []
    for pid in ALL_PROVIDERS:
        ok, detail = provider_configured(pid, cfg)
        out.append(
            ProviderConfig(
                id=pid,
                label=labels[pid],
                configured=ok,
                model_default=default_model(pid, cfg),
                model_current=default_model(pid, cfg) if pid == active else default_model(pid, cfg),
                detail=detail if ok else f"Não configurado — {detail}",
            )
        )
    return out


def _anthropic_complete(api_key: str, model: str, system: str, user_prompt: str, timeout: float) -> str:
    payload = {
        "model": model,
        "max_tokens": 4096,
        "temperature": 0.35,
        "system": system,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    blocks = data.get("content") or []
    texts = [b.get("text") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    return "".join(str(t) for t in texts if t)


def _openai_complete(api_key: str, model: str, system: str, user_prompt: str, timeout: float) -> str:
    payload = {
        "model": model,
        "temperature": 0.35,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {"authorization": f"Bearer {api_key}", "content-type": "application/json"}
    with httpx.Client(timeout=timeout) as client:
        r = client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        return ""
    return str((choices[0].get("message") or {}).get("content") or "")


def _gemini_complete(api_key: str, model: str, system: str, user_prompt: str, timeout: float) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.35, "maxOutputTokens": 4096},
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))


def _grok_complete(api_key: str, model: str, system: str, user_prompt: str, timeout: float) -> str:
    payload = {
        "model": model,
        "temperature": 0.35,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {"authorization": f"Bearer {api_key}", "content-type": "application/json"}
    with httpx.Client(timeout=timeout) as client:
        r = client.post("https://api.x.ai/v1/chat/completions", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        return ""
    return str((choices[0].get("message") or {}).get("content") or "")


def complete_text(
    *,
    system: str,
    user_prompt: str,
    provider: ProviderId | None = None,
    cfg: dict[str, Any] | None = None,
) -> tuple[str, ProviderId, str]:
    """Retorna (texto, provider_usado, model)."""

    settings = cfg or resolve_provider_settings()
    pid: ProviderId = (provider or settings["provider"])  # type: ignore[assignment]
    if pid not in ALL_PROVIDERS:
        pid = "ollama"
    model = default_model(pid, settings)
    timeout = float(settings["timeout"])

    ok, _ = provider_configured(pid, settings)
    if not ok and pid != "ollama":
        pid = "ollama"
        model = default_model("ollama", settings)

    if pid == "anthropic":
        text = _anthropic_complete(
            settings["anthropic_api_key"],
            model,
            system,
            user_prompt,
            timeout,
        )
    elif pid == "openai":
        text = _openai_complete(
            settings["openai_api_key"],
            model,
            system,
            user_prompt,
            timeout,
        )
    elif pid == "gemini":
        text = _gemini_complete(
            settings["gemini_api_key"],
            model,
            system,
            user_prompt,
            timeout,
        )
    elif pid == "grok":
        text = _grok_complete(
            settings["grok_api_key"],
            model,
            system,
            user_prompt,
            timeout,
        )
    elif pid in ("groq", "openrouter"):
        base = "https://api.groq.com/openai/v1" if pid == "groq" else "https://openrouter.ai/api/v1"
        key = settings["groq_api_key"] if pid == "groq" else settings["openrouter_api_key"]
        text = _openai_compatible_chat(
            base_url=base,
            api_key=key,
            model=model,
            system=system + "\n\nResponda SOMENTE com JSON válido.",
            user_prompt=user_prompt,
            timeout=timeout,
            temperature=0.35,
        )
    elif pid in ("ollama", "openai_compatible"):
        base = settings["openai_compatible_base_url"] or OLLAMA_DEFAULT_OPENAI_API_BASE
        key = settings["openai_compatible_api_key"] or None
        suffix = "\n\nResponda SOMENTE com JSON válido, sem markdown."
        text = _openai_compatible_chat(
            base_url=base,
            api_key=key,
            model=model,
            system=system + suffix,
            user_prompt=user_prompt,
            timeout=timeout,
            temperature=0.35,
        )
    else:
        raise RuntimeError(f"Provedor não suportado: {pid}")

    return text.strip(), pid, model


def parse_json_array(raw: str) -> list[dict[str, Any]]:
    text = _strip_json_fence(raw)
    # objeto único com chave ideas
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"IA retornou JSON inválido: {exc}") from exc
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("ideas", "ideias", "posts", "items"):
            val = data.get(key)
            if isinstance(val, list):
                return val
        if "titulo" in data or "legenda" in data:
            return [data]
    raise RuntimeError("Resposta da IA não é lista de ideias")


def compare_providers(
    *,
    system: str,
    user_prompt: str,
    providers: tuple[ProviderId, ...] | None = None,
) -> list[dict[str, Any]]:
    """Chamada comparativa (uso posterior no dashboard)."""

    cfg = resolve_provider_settings()
    targets = providers or tuple(
        p for p in ALL_PROVIDERS if provider_configured(p, cfg)[0]
    )
    results: list[dict[str, Any]] = []
    for pid in targets:
        try:
            text, used, model = complete_text(
                system=system, user_prompt=user_prompt, provider=pid, cfg=cfg
            )
            ideas = parse_json_array(text)
            results.append(
                {
                    "provider": used,
                    "model": model,
                    "ok": True,
                    "ideas_count": len(ideas),
                    "preview": (ideas[0].get("gancho") or ideas[0].get("titulo") or "")[:200],
                }
            )
        except Exception as exc:
            results.append(
                {
                    "provider": pid,
                    "model": default_model(pid, cfg),
                    "ok": False,
                    "error": str(exc)[:500],
                }
            )
    return results
