"""Geração de imagens — OpenAI, Gemini, Pillow (local); status por provedor."""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from naintegra_meta.ai_providers import _first_env, resolve_provider_settings
from naintegra_meta.carousel_renderer import render_slide
from naintegra_meta.marketing_library import (
    get_image_prompt_for_slide,
    load_bundled_library,
    marketing_image_model,
)

logger = logging.getLogger(__name__)

ImageProviderId = Literal["openai", "gemini", "pillow", "none"]

ALL_IMAGE_PROVIDERS: tuple[ImageProviderId, ...] = ("openai", "gemini", "pillow")


@dataclass(frozen=True)
class ImageProviderStatus:
    id: ImageProviderId
    label: str
    configured: bool
    model: str
    detail: str


def image_provider_configured(pid: ImageProviderId) -> tuple[bool, str, str]:
    lib = load_bundled_library()
    if pid == "pillow":
        return True, "pillow-local", "Render PIL (sempre disponível)"
    if pid == "openai":
        key = _first_env("DELEGADO_OPENAI_API_KEY", "OPENAI_API_KEY", "LEX_AGENT_OPENAI_API_KEY")
        model = _first_env("DELEGADO_OPENAI_IMAGE_MODEL") or "dall-e-3"
        return bool(key), model, "DALL-E / gpt-image"
    if pid == "gemini":
        key = _first_env(
            "DELEGADO_GEMINI_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "GOOGLE_GENERATIVE_AI_API_KEY",
        )
        model = marketing_image_model()
        return bool(key), model, "Gemini (Marketing Digital slides)"
    return False, "", "desconhecido"


def list_image_provider_statuses() -> list[ImageProviderStatus]:
    labels = {"openai": "OpenAI DALL-E", "gemini": "Google Gemini Imagen", "pillow": "Local (PIL)"}
    out: list[ImageProviderStatus] = []
    for pid in ALL_IMAGE_PROVIDERS:
        ok, model, detail = image_provider_configured(pid)
        out.append(
            ImageProviderStatus(
                id=pid,
                label=labels[pid],
                configured=ok,
                model=model,
                detail=detail if ok else f"Configure chave — {detail}",
            )
        )
    return out


def _style_prefix() -> str:
    lib = load_bundled_library()
    return str(lib.get("image_style_prompt") or "Professional legal education Instagram slide")


def generate_openai_image(prompt: str, out_path: Path, *, size: str = "1024x1024") -> Path:
    key = _first_env("DELEGADO_OPENAI_API_KEY", "OPENAI_API_KEY", "LEX_AGENT_OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY não configurada")
    model = _first_env("DELEGADO_OPENAI_IMAGE_MODEL") or "dall-e-3"
    payload = {
        "model": model,
        "prompt": f"{_style_prefix()}. {prompt}"[:4000],
        "n": 1,
        "size": size,
        "response_format": "b64_json",
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=180.0) as client:
        r = client.post("https://api.openai.com/v1/images/generations", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    b64 = ((data.get("data") or [{}])[0]).get("b64_json")
    if not b64:
        raise RuntimeError("OpenAI não retornou imagem")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(b64))
    return out_path


def _gemini_slide_text(prompt: str, slide_title: str, slide_body: str) -> str:
    if slide_title or slide_body:
        parts = [p for p in (slide_title.strip(), slide_body.strip()) if p]
        return "\n".join(parts) if parts else prompt[:2000]
    return prompt[:2000]


def generate_gemini_image(
    prompt: str,
    out_path: Path,
    *,
    slide_title: str = "",
    slide_body: str = "",
) -> Path:
    """Gera slide no padrão Marketing Digital (fundo branco, texto preto)."""

    key = _first_env(
        "DELEGADO_GEMINI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_GENERATIVE_AI_API_KEY",
    )
    if not key:
        raise RuntimeError("GEMINI_API_KEY não configurada")
    model = marketing_image_model()
    slide_text = _gemini_slide_text(prompt, slide_title, slide_body)
    text_prompt = get_image_prompt_for_slide(slide_text)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    body = {
        "contents": [{"role": "user", "parts": [{"text": text_prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
            "responseMimeType": "text/plain",
        },
    }
    with httpx.Client(timeout=180.0) as client:
        r = client.post(url, json=body)
        if r.status_code >= 400 and "image-preview" not in model:
            legacy = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.0-flash-preview-image-generation:generateContent?key={key}"
            )
            r = client.post(legacy, json=body)
        r.raise_for_status()
        data = r.json()

    b64 = None
    for cand in data.get("candidates") or []:
        for part in (cand.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                b64 = inline["data"]
                break
    if not b64:
        raise RuntimeError(f"Gemini imagem: resposta sem bytes ({str(data)[:300]})")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(b64))
    return out_path


def generate_image(
    prompt: str,
    out_path: Path,
    *,
    provider: ImageProviderId | None = None,
    slide_title: str = "",
    slide_body: str = "",
) -> tuple[Path, ImageProviderId, str]:
    """Tenta provedor pedido; fallback pillow com texto do slide."""

    preferred = provider or (_first_env("DELEGADO_IMAGE_PROVIDER") or "pillow")  # type: ignore[assignment]
    order: list[ImageProviderId] = []
    if preferred in ALL_IMAGE_PROVIDERS:
        order.append(preferred)
    for p in ALL_IMAGE_PROVIDERS:
        if p not in order:
            order.append(p)

    last_err = ""
    for pid in order:
        if not image_provider_configured(pid)[0]:
            continue
        try:
            if pid == "openai":
                return generate_openai_image(prompt, out_path), "openai", "dall-e-3"
            if pid == "gemini":
                _, model, _ = image_provider_configured("gemini")
                return (
                    generate_gemini_image(
                        prompt,
                        out_path,
                        slide_title=slide_title,
                        slide_body=slide_body,
                    ),
                    "gemini",
                    model,
                )
            if pid == "pillow":
                render_slide(
                    title=slide_title or "NaIntegra",
                    body=slide_body or prompt[:300],
                    out_path=out_path,
                )
                return out_path, "pillow", "local-pil"
        except Exception as exc:
            logger.warning("Imagem %s falhou: %s", pid, exc)
            last_err = str(exc)
            continue

    render_slide(title=slide_title or "Post", body=slide_body or prompt[:300], out_path=out_path)
    return out_path, "pillow", f"fallback ({last_err[:80]})"
