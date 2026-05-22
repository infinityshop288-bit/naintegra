from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from ..ai_cache import AIDecisionCache
from ..ai_organizer import _openai_compatible_chat, default_ai_model
from .prompts import (
    SYSTEM_STUDY,
    SYSTEM_STUDY_CITED_SOLUTION,
    USER_STUDY_WRAPPER,
    USER_STUDY_WRAPPER_CITED,
)
from .settings import QConcursoStudySettings

logger = logging.getLogger(__name__)


def study_system_prompt(settings: QConcursoStudySettings) -> str:
    if settings.study_prompt_profile == "cited_solution":
        return SYSTEM_STUDY_CITED_SOLUTION
    return SYSTEM_STUDY


def _anthropic_complete(
    *,
    api_key: str,
    model: str,
    system: str,
    user_prompt: str,
    timeout: float,
    max_tokens: int = 8192,
) -> str:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.25,
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


def _openai_complete(*, api_key: str, model: str, system: str, user_prompt: str, timeout: float) -> str:
    payload = {
        "model": model,
        "temperature": 0.25,
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
    msg = choices[0].get("message") or {}
    return str(msg.get("content") or "")


def _alternativas_block(alt: dict[str, str]) -> str:
    lines = [f"- ({k}) {alt[k]}" for k in sorted(alt.keys())]
    return "\n".join(lines) if lines else "(Sem alternativas estruturadas no crawl.)"


def study_cache_key(stem_key_value: str, settings: QConcursoStudySettings) -> str:
    return f"study_v2:{settings.study_prompt_profile}:{stem_key_value}"


def build_user_prompt(row: dict[str, Any], settings: QConcursoStudySettings) -> str:
    enunciado = str(row["enunciado"])
    disciplina = row.get("disciplina") or ""
    gab = row.get("_gabarito_letter_hidden") or "?"
    usr = row.get("_user_wrong_letter_hidden") or "?"
    wrapper = (
        USER_STUDY_WRAPPER_CITED
        if settings.study_prompt_profile == "cited_solution"
        else USER_STUDY_WRAPPER
    )
    return wrapper.format(
        disciplina=disciplina or "(não informada)",
        gabarito_letter=gab,
        user_letter=usr,
        enunciado=enunciado[:12000],
        alternativas_block=_alternativas_block(dict(row.get("alternativas") or {})),
    )


def call_study_ai(
    settings: QConcursoStudySettings,
    user_prompt: str,
) -> str:
    model = settings.ai_model or default_ai_model(settings.ai_provider)
    system = study_system_prompt(settings)

    if settings.ai_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("Defina QC_STUDY_ANTHROPIC_API_KEY no .env.")
        return _anthropic_complete(
            api_key=settings.anthropic_api_key,
            model=model,
            system=system,
            user_prompt=user_prompt,
            timeout=settings.ai_timeout_seconds,
        )

    if settings.ai_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("Defina QC_STUDY_OPENAI_API_KEY no .env.")
        return _openai_complete(
            api_key=settings.openai_api_key,
            model=model,
            system=system,
            user_prompt=user_prompt,
            timeout=settings.ai_timeout_seconds,
        )

    if settings.ai_provider in ("openai_compatible", "ollama"):
        root = settings.resolved_openai_compatible_base_url()
        if not root:
            raise RuntimeError(
                "Defina QC_STUDY_OPENAI_COMPATIBLE_BASE_URL (ex.: http://127.0.0.1:11434/v1 para servidor local)."
            )
        key = (settings.openai_compatible_api_key or "").strip() or None
        return _openai_compatible_chat(
            base_url=root,
            api_key=key,
            model=model,
            system=system,
            user_prompt=user_prompt,
            timeout=settings.ai_timeout_seconds,
            temperature=0.25,
        )

    raise RuntimeError(f"QC_STUDY_AI_PROVIDER desconhecido: {settings.ai_provider}")


def json_payload_doc(
    row: dict[str, Any],
    markdown: str,
    *,
    study_prompt_profile: str,
) -> dict[str, Any]:
    return {
        "stem_key": row["stem_key"],
        "disciplina": row.get("disciplina"),
        "merged_source_ids": row.get("merged_source_ids") or [],
        "markdown": markdown,
        "alternativas": row.get("alternativas"),
        "enunciado": row["enunciado"],
        "study_prompt_profile": study_prompt_profile,
    }


def write_study_bundle(
    settings: QConcursoStudySettings,
    row: dict[str, Any],
    markdown: str,
) -> Path:
    studies_dir = Path(settings.studies_dir)
    studies_dir.mkdir(parents=True, exist_ok=True)
    doc = json_payload_doc(
        row,
        markdown,
        study_prompt_profile=settings.study_prompt_profile,
    )
    out_json = studies_dir / f'{row["stem_key"]}.json'
    cache = AIDecisionCache(Path(settings.studies_cache_sqlite))
    try:
        cache.set(study_cache_key(str(row["stem_key"]), settings), doc)
        out_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        cache.close()
    return out_json


def sync_cache_to_disk(settings: QConcursoStudySettings, row: dict[str, Any]) -> bool:
    stem = str(row["stem_key"])
    cache = AIDecisionCache(Path(settings.studies_cache_sqlite))
    try:
        cached = cache.get(study_cache_key(stem, settings))
    finally:
        cache.close()

    if not isinstance(cached, dict) or not (cached.get("markdown") or "").strip():
        return False

    doc = dict(cached)
    doc.setdefault("stem_key", stem)
    doc["alternativas"] = row.get("alternativas")
    doc["enunciado"] = row["enunciado"]
    doc["disciplina"] = row.get("disciplina")
    doc.setdefault("merged_source_ids", row.get("merged_source_ids") or [])
    doc.setdefault("study_prompt_profile", settings.study_prompt_profile)
    Path(settings.studies_dir).mkdir(parents=True, exist_ok=True)
    out_json = Path(settings.studies_dir) / f"{stem}.json"
    out_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def run_study_for_consolidated(
    settings: QConcursoStudySettings,
    row: dict[str, Any],
    *,
    force: bool = False,
) -> Path | None:
    stem = str(row["stem_key"])
    out_json = Path(settings.studies_dir) / f"{stem}.json"
    Path(settings.studies_dir).mkdir(parents=True, exist_ok=True)

    if not force and out_json.is_file():
        logger.debug("%s já tem JSON em disco.", out_json.name)
        return out_json

    if not force and sync_cache_to_disk(settings, row):
        return Path(settings.studies_dir) / f"{stem}.json"

    up = build_user_prompt(row, settings)
    if len(up) > settings.ai_max_input_chars:
        up = up[: settings.ai_max_input_chars]

    text = call_study_ai(settings, up)
    if not text.strip():
        logger.warning("IA vazia stem=%s", stem[:14])
        return None
    out_path = write_study_bundle(settings, row, text.strip())
    logger.info("Estudo gravado %s", out_path.name)
    return out_path


def bulk_study(
    settings: QConcursoStudySettings,
    consolidated_lines: list[dict[str, Any]],
    *,
    force: bool = False,
    max_new: int | None = None,
) -> int:
    cap = settings.study_max_batches if max_new is None else max_new
    delay = settings.ai_calls_delay_seconds
    Path(settings.studies_dir).mkdir(parents=True, exist_ok=True)

    cache = AIDecisionCache(Path(settings.studies_cache_sqlite))

    try:
        n_calls = 0
        for row in consolidated_lines:
            stem = str(row["stem_key"])
            sk = study_cache_key(stem, settings)
            out_json = Path(settings.studies_dir) / f"{stem}.json"

            if not force:
                if out_json.is_file():
                    continue
                if sync_cache_to_disk(settings, row):
                    continue

            if n_calls >= cap:
                logger.warning("Limite de novos estudos nesta rodada (%s); parando.", cap)
                break

            up = build_user_prompt(row, settings)
            if len(up) > settings.ai_max_input_chars:
                up = up[: settings.ai_max_input_chars]

            text = call_study_ai(settings, up)
            if not text.strip():
                logger.warning("IA vazia stem=%s (pulando)", stem[:14])
                continue

            doc = json_payload_doc(
                row,
                text.strip(),
                study_prompt_profile=settings.study_prompt_profile,
            )
            cache.set(sk, doc)
            out_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
            n_calls += 1
            logger.info("Novo estudo %s", out_json.name)
            if delay > 0:
                time.sleep(delay)

    finally:
        cache.close()
    return n_calls
