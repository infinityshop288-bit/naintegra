"""Chamada direta aos provedores de IA, sem depender de Edge Function.

Ordem de tentativa: groq → github (GitHub Models) → gemini → openrouter → claude.
As chaves vêm do ambiente ou do .env da raiz do projeto. No GitHub Actions o
provedor `github` funciona com o GITHUB_TOKEN automático, desde que o job
declare `permissions: models: read` — ou seja, não exige chave própria.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]

PRIORIDADE = ("groq", "github", "gemini", "openrouter", "claude")

CHAVES = {
    "groq": "GROQ_API_KEY",
    "github": "GITHUB_TOKEN",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}

MODELOS = {
    "groq": "llama-3.3-70b-versatile",
    "github": "openai/gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "openrouter": "meta-llama/llama-3.3-70b-instruct",
    "claude": "claude-sonnet-4-20250514",
}

# modelos preferidos no Groq — a lista deles muda com frequência
GROQ_PREFERIDOS = (
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "moonshotai/kimi-k2-instruct",
    "qwen/qwen3-32b",
    "llama-3.1-8b-instant",
)

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    _SSL = ssl._create_unverified_context()

_groq_modelo: str | None = None
_env_arquivo: dict[str, str] | None = None


def _do_env(nome: str) -> str | None:
    """Chave do ambiente; se ausente, procura no .env da raiz do repositório."""
    global _env_arquivo
    if os.environ.get(nome):
        return os.environ[nome]
    if _env_arquivo is None:
        _env_arquivo = {}
        for arq in (REPO / ".env", ROOT / ".env"):
            if not arq.is_file():
                continue
            for linha in arq.read_text(encoding="utf-8", errors="replace").splitlines():
                linha = linha.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                k, v = linha.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if v:
                    _env_arquivo.setdefault(k.strip(), v)
    return _env_arquivo.get(nome)


def _post(url: str, payload: dict, headers: dict, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"{e.code}: {detalhe}") from None


def _openai_like(url: str, key: str, modelo: str, msgs: list[dict], max_tokens: int) -> str:
    data = _post(
        url,
        {"model": modelo, "max_tokens": max_tokens, "messages": msgs, "temperature": 0.7},
        {"Authorization": f"Bearer {key}"},
    )
    return (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""


def _descobre_modelo_groq(key: str) -> str:
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"}
    )
    with urllib.request.urlopen(req, timeout=30, context=_SSL) as r:
        ids = [m["id"] for m in (json.loads(r.read().decode()).get("data") or [])]
    for m in GROQ_PREFERIDOS:
        if m in ids:
            return m
    livres = [i for i in ids if not any(x in i for x in ("whisper", "guard", "tts", "embed"))]
    if not livres:
        raise RuntimeError("Groq sem modelo de chat disponível")
    return livres[0]


def _groq(msgs: list[dict], max_tokens: int) -> str:
    global _groq_modelo
    key = _do_env("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY ausente")
    url = "https://api.groq.com/openai/v1/chat/completions"
    modelo = _groq_modelo or os.environ.get("GROQ_MODEL") or MODELOS["groq"]
    try:
        out = _openai_like(url, key, modelo, msgs, max_tokens)
    except RuntimeError as e:
        if not any(t in str(e).lower() for t in ("model_not_found", "does not exist", "decommission", "deprecat")):
            raise
        modelo = _descobre_modelo_groq(key)
        out = _openai_like(url, key, modelo, msgs, max_tokens)
    _groq_modelo = modelo
    return out


def _github(msgs: list[dict], max_tokens: int) -> str:
    key = _do_env("GITHUB_TOKEN")
    if not key:
        raise RuntimeError("GITHUB_TOKEN ausente")
    modelo = os.environ.get("GITHUB_MODEL") or MODELOS["github"]
    return _openai_like("https://models.github.ai/inference/chat/completions", key, modelo, msgs, max_tokens)


def _openrouter(msgs: list[dict], max_tokens: int) -> str:
    key = _do_env("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY ausente")
    modelo = os.environ.get("OPENROUTER_MODEL") or MODELOS["openrouter"]
    return _openai_like("https://openrouter.ai/api/v1/chat/completions", key, modelo, msgs, max_tokens)


def _gemini(msgs: list[dict], max_tokens: int) -> str:
    key = _do_env("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY ausente")
    modelo = os.environ.get("GEMINI_MODEL") or MODELOS["gemini"]
    conteudos: list[dict] = []
    for m in msgs:
        if m["role"] == "system":
            conteudos.append({"role": "user", "parts": [{"text": m["content"]}]})
            conteudos.append({"role": "model", "parts": [{"text": "Entendido."}]})
        else:
            papel = "model" if m["role"] == "assistant" else "user"
            conteudos.append({"role": papel, "parts": [{"text": m["content"]}]})
    data = _post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={key}",
        {"contents": conteudos, "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens}},
        {},
    )
    partes = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}]
    return partes[0].get("text") or ""


def _claude(msgs: list[dict], max_tokens: int) -> str:
    key = _do_env("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY ausente")
    sistema = next((m["content"] for m in msgs if m["role"] == "system"), "")
    data = _post(
        "https://api.anthropic.com/v1/messages",
        {
            "model": os.environ.get("CLAUDE_MODEL") or MODELOS["claude"],
            "max_tokens": max_tokens,
            "system": sistema,
            "messages": [m for m in msgs if m["role"] != "system"],
            "temperature": 0.7,
        },
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    return (data.get("content") or [{}])[0].get("text") or ""


_FUNCOES = {
    "groq": _groq,
    "github": _github,
    "gemini": _gemini,
    "openrouter": _openrouter,
    "claude": _claude,
}


def configurados() -> list[str]:
    return [p for p in PRIORIDADE if _do_env(CHAVES[p])]


def chat(msgs: list[dict], max_tokens: int = 2048, preferido: str | None = None) -> tuple[str, str]:
    """Tenta os provedores em ordem; devolve (conteúdo, provedor)."""
    ordem = ([preferido] if preferido in _FUNCOES else []) + [p for p in PRIORIDADE if p != preferido]
    erros = []
    for p in ordem:
        if not _do_env(CHAVES[p]):
            continue
        try:
            out = _FUNCOES[p](msgs, max_tokens)
            if out.strip():
                return out, p
            erros.append(f"{p}: resposta vazia")
        except Exception as e:  # noqa: BLE001
            erros.append(f"{p}: {e}")
    raise RuntimeError("nenhum provedor respondeu — " + " | ".join(erros or ["sem chaves configuradas"]))


def gerar(prompt: str, max_tokens: int = 2048, preferido: str | None = None) -> tuple[str, str]:
    return chat(
        [
            {"role": "system", "content": "Responda em português do Brasil. Seja preciso e objetivo."},
            {"role": "user", "content": prompt},
        ],
        max_tokens,
        preferido,
    )
