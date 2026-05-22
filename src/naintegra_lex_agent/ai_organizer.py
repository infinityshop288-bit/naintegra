from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from .legal_text import pick_display_title, pick_explicacao, pick_verbatim_body
from .schemas import DocType, NormalizedDocument, content_hash
from .exam_questions import enrich_questoes_meta
from .taxonomy import canonical_banca, canonical_materia, canonical_tribunal

logger = logging.getLogger(__name__)

_ALLOWED_TYPES = frozenset(
    {
        "legislacao",
        "jurisprudencia",
        "sumula",
        "questoes_objetivas",
        "questoes_subjetivas",
    }
)


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def parse_ai_json(raw_text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(_strip_json_fence(raw_text))
    except json.JSONDecodeError:
        logger.warning("IA retornou JSON inválido")
        return None
    if not isinstance(data, dict):
        return None
    return validate_ai_payload(data)


def validate_ai_payload(data: dict[str, Any]) -> dict[str, Any] | None:
    dt = data.get("doc_type")
    if dt not in _ALLOWED_TYPES:
        return None
    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    tribunal = canonical_tribunal(data.get("tribunal"))
    materia = canonical_materia(data.get("materia"))
    banca = canonical_banca(data.get("banca"))

    secao = data.get("secao_lei_seca")
    secao_str = str(secao).strip() if secao not in (None, "") else None

    tags = data.get("tags_incidencia")
    if tags is None:
        tags_list: list[str] = []
    elif isinstance(tags, list):
        tags_list = [str(x) for x in tags if x is not None][:30]
    else:
        tags_list = []

    short_label = data.get("short_label")
    rationale = data.get("rationale")

    ano_raw = data.get("ano")
    ano: int | None = None
    if ano_raw is not None:
        try:
            ano = int(ano_raw)
        except (TypeError, ValueError):
            ano = None

    cargo = data.get("cargo")
    cargo_str = str(cargo).strip() if cargo not in (None, "") else None

    nq = data.get("numero_questao")
    numero_questao = str(nq).strip() if nq not in (None, "") else None

    fmt_q = data.get("formato_questao")
    formato_questao = str(fmt_q).strip() if fmt_q not in (None, "") else None

    organized: dict[str, Any] = {}
    if tribunal:
        organized["tribunal"] = tribunal
    if materia:
        organized["materia"] = materia
    if banca:
        organized["banca"] = banca
    if ano is not None:
        organized["ano"] = ano
    if cargo_str:
        organized["cargo"] = cargo_str
    if numero_questao:
        organized["numero_questao"] = numero_questao
    if formato_questao:
        organized["formato_questao"] = formato_questao
    if secao_str:
        organized["secao_lei_seca"] = secao_str
    if tags_list:
        organized["tags_incidencia"] = tags_list

    return {
        "doc_type": dt,
        "organized": organized,
        "confidence": confidence,
        "short_label": str(short_label).strip() if short_label else None,
        "rationale": str(rationale).strip() if rationale else None,
    }


def _snippet(record: dict[str, Any], max_chars: int) -> str:
    body = pick_verbatim_body(record) or ""
    parts = [
        str(pick_display_title(record) or ""),
        str(body),
        str(record.get("type") or record.get("doc_type") or ""),
        json.dumps(record.get("metadata") or record.get("meta") or {}, ensure_ascii=False),
    ]
    blob = "\n---\n".join(parts)
    return blob[:max_chars]


def ai_cache_key(external_id: str, record: dict[str, Any]) -> str:
    return content_hash(
        {
            "external_id": external_id,
            "snippet": _snippet(record, 6000),
        }
    )


SYSTEM_PROMPT = """Você classifica e organiza documentos jurídicos brasileiros para o app NaIntegra Lex (concurseiros).

Responda APENAS com um objeto JSON (sem markdown) usando exatamente estas chaves:
{
  "doc_type": "legislacao" | "jurisprudencia" | "sumula" | "questoes_objetivas" | "questoes_subjetivas",
  "tribunal": "STF"|"STJ"|"TST"|"TSE"|null,
  "materia": "Penal"|"Administrativo"|"Processual"|"Tributário"|"Constitucional"|"Civil"|"Trabalho"|"Eleitoral"|null,
  "banca": string curta em MAIÚSCULAS (ex.: "CESPE", "FGV") ou null,
  "ano": número do ano da prova ou null,
  "cargo": string curta do cargo ou null,
  "numero_questao": string ou número como string (ex.: "37") ou null,
  "formato_questao": "objetiva"|"subjetiva"|"multipla_escolha"|"certo_errado"|null,
  "secao_lei_seca": string curta para agrupar no Lei Seca (ex.: "Penal e Processual") ou null,
  "tags_incidencia": ["PF","CESPE", "..."] ou [],
  "confidence": número entre 0 e 1,
  "short_label": string curta opcional ou null,
  "rationale": uma frase curta em pt-BR explicando a classificação
}

Regras:
- súmulas ou enunciados numerados de tribunal → "sumula" quando for súmula; caso contrário jurisprudência.
- leis, MPs, decretos, instruções normativas → "legislacao".
- questões de prova com alternativas / múltipla escolha / certo-errado → "questoes_objetivas".
- questões discursivas sem alternativas formais → "questoes_subjetivas".
- Se não souber tribunal/matéria/banca, use null (não invente).
"""

# Endpoint OpenAI-compatível padrão do Ollama local.
OLLAMA_DEFAULT_OPENAI_API_BASE = "http://127.0.0.1:11434/v1"

_SYSTEM_PROMPT_LOCAL_COMPAT_SUFFIX = (
    "\n\nSaída obrigatória: somente o objeto JSON pedido acima, "
    "sem markdown (sem ```json), sem texto antes ou depois."
)


def organizer_system_prompt(*, local_openai_compat: bool) -> str:
    """Reforço de formato JSON para Ollama / LM Studio / vLLM (sem ``response_format`` da OpenAI)."""

    if local_openai_compat:
        return SYSTEM_PROMPT + _SYSTEM_PROMPT_LOCAL_COMPAT_SUFFIX
    return SYSTEM_PROMPT


def _anthropic_complete(api_key: str, model: str, user_prompt: str, timeout: float) -> str:
    payload = {
        "model": model,
        "max_tokens": 1024,
        "temperature": 0.2,
        "system": SYSTEM_PROMPT,
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


def _openai_complete(api_key: str, model: str, user_prompt: str, timeout: float) -> str:
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
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


def _openai_compatible_chat(
    *,
    base_url: str,
    api_key: str | None,
    model: str,
    system: str,
    user_prompt: str,
    timeout: float,
    temperature: float,
) -> str:
    """POST `{base}/chat/completions` — Ollama, LM Studio, vLLM, etc."""

    root = base_url.rstrip("/")
    url = f"{root}/chat/completions"
    headers = {"content-type": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return str(msg.get("content") or "")


def default_ai_model(provider: str) -> str:
    if provider == "anthropic":
        return "claude-sonnet-4-20250514"
    if provider == "openai":
        return "gpt-4o-mini"
    if provider in ("openai_compatible", "ollama"):
        return "llama3.2"
    return "gpt-4o-mini"


def call_organizer_ai(
    *,
    provider: str,
    api_key: str,
    model: str,
    record: dict[str, Any],
    external_id: str,
    timeout: float,
    max_input_chars: int,
    enrich_hint: str | None = None,
    openai_compatible_base_url: str | None = None,
) -> dict[str, Any] | None:
    hint_block = f"\nInstrução extra:\n{enrich_hint}\n" if enrich_hint else ""
    user_prompt = (
        "Analise o registro abaixo e produza o JSON pedido.\n"
        f"external_id informado: {external_id}\n"
        f"{hint_block}\n"
        "--- REGISTRO (pode estar incompleto) ---\n"
        f"{_snippet(record, max_input_chars)}"
    )

    try:
        if provider == "anthropic":
            raw_text = _anthropic_complete(api_key, model, user_prompt, timeout)
        elif provider == "openai":
            raw_text = _openai_complete(api_key, model, user_prompt, timeout)
        elif provider in ("openai_compatible", "ollama"):
            root = (openai_compatible_base_url or "").strip()
            if provider == "ollama" and not root:
                root = OLLAMA_DEFAULT_OPENAI_API_BASE
            if not root:
                logger.error(
                    "openai_compatible sem base URL (LEX_AGENT_OPENAI_COMPATIBLE_BASE_URL ou QC_STUDY_*)"
                )
                return None
            key = api_key.strip() if api_key else None
            raw_text = _openai_compatible_chat(
                base_url=root,
                api_key=key,
                model=model,
                system=organizer_system_prompt(local_openai_compat=True),
                user_prompt=user_prompt,
                timeout=timeout,
                temperature=0.2,
            )
        else:
            logger.error("Provedor IA desconhecido: %s", provider)
            return None
    except Exception:
        logger.exception("Falha na chamada ao provedor IA (%s)", provider)
        return None

    validated = parse_ai_json(raw_text)
    if not validated:
        logger.warning("IA retornou payload inválido após parse")
    return validated


def merge_ai_enrichment(base: NormalizedDocument, ai: dict[str, Any]) -> NormalizedDocument:
    """Preserva doc_type heurístico; completa organized/meta. Não altera título/texto coletados."""

    merged_org = dict(base.organized)
    org_ai = ai.get("organized") or {}
    if isinstance(org_ai, dict):
        for k, v in org_ai.items():
            if v is None:
                continue
            if k not in merged_org or merged_org[k] in (None, "", []):
                merged_org[k] = v

    sl = ai.get("short_label")
    if sl:
        merged_org["rotulo_sugerido_ia"] = str(sl).strip()

    meta = dict(base.meta)
    meta["ai_enriched"] = True
    meta["ai_confidence"] = ai.get("confidence")
    if ai.get("rationale"):
        meta["ai_rationale"] = ai["rationale"]

    fingerprint = content_hash(
        {
            "external_id": base.external_id,
            "doc_type": base.doc_type.value,
            "title": base.title,
            "body": (base.body or "")[:8000],
            "meta": meta,
            "organized": merged_org,
        }
    )

    return NormalizedDocument(
        external_id=base.external_id,
        doc_type=base.doc_type,
        source_system=base.source_system,
        title=base.title,
        body=base.body,
        meta=meta,
        organized=merged_org,
        crawl_batch_id=base.crawl_batch_id,
        raw_fingerprint=fingerprint,
        preservation=dict(base.preservation),
    )


def document_from_ai_only(
    *,
    external_id: str,
    ai: dict[str, Any],
    raw: dict[str, Any],
    from_cache: bool,
    ai_mode_label: str,
    preservation: dict[str, Any],
) -> NormalizedDocument | None:
    doc_type_str = ai["doc_type"]
    try:
        doc_type = DocType(doc_type_str)
    except ValueError:
        return None

    title = pick_display_title(raw)
    body = pick_verbatim_body(raw)
    if not (title or body):
        return None

    organized_ai = dict(ai.get("organized") or {})
    if not isinstance(organized_ai, dict):
        organized_ai = {}
    if ai.get("short_label"):
        organized_ai["rotulo_sugerido_ia"] = str(ai["short_label"]).strip()

    meta: dict[str, Any] = {
        "ai_fallback": True,
        "ai_cached": from_cache,
        "ai_mode": ai_mode_label,
        "ai_confidence": ai.get("confidence"),
    }
    if ai.get("rationale"):
        meta["ai_rationale"] = ai["rationale"]

    exp = pick_explicacao(raw)
    if exp:
        meta["explicacao"] = exp

    meta = enrich_questoes_meta(meta, raw, doc_type)

    source_system = raw.get("source_system") or raw.get("source")
    batch_id = raw.get("crawl_batch_id") or raw.get("batch_id")

    fingerprint = content_hash(
        {
            "external_id": external_id,
            "doc_type": doc_type.value,
            "title": title,
            "body": (str(body) if body else "")[:8000],
            "meta": meta,
            "organized": organized_ai,
        }
    )

    return NormalizedDocument(
        external_id=external_id,
        doc_type=doc_type,
        source_system=str(source_system) if source_system else None,
        title=str(title) if title else None,
        body=str(body) if body else None,
        meta=meta,
        organized=dict(organized_ai),
        crawl_batch_id=str(batch_id) if batch_id else None,
        raw_fingerprint=fingerprint,
        preservation=dict(preservation),
    )


def needs_enrichment(doc: NormalizedDocument) -> bool:
    org = doc.organized
    if doc.doc_type in (DocType.JURISPRUDENCIA, DocType.SUMULA):
        return org.get("tribunal") in (None, "") or org.get("materia") in (None, "")
    if doc.doc_type == DocType.LEGISLACAO:
        return org.get("secao_lei_seca") in (None, "")
    if doc.doc_type in (DocType.QUESTOES_OBJETIVAS, DocType.QUESTOES_SUBJETIVAS):
        return org.get("materia") in (None, "") or org.get("banca") in (None, "")
    return False


def merge_full_ai_preference(base: NormalizedDocument, ai: dict[str, Any]) -> NormalizedDocument:
    """Modo full: pode realinhar doc_type/organized da IA; titulo/texto permanecem os coletados."""

    try:
        ai_type = DocType(str(ai["doc_type"]))
    except ValueError:
        ai_type = base.doc_type

    merged_org = dict(ai.get("organized") or {})
    sl = ai.get("short_label")
    if sl:
        merged_org["rotulo_sugerido_ia"] = str(sl).strip()

    meta = dict(base.meta)
    meta["ai_full"] = True
    meta["ai_confidence"] = ai.get("confidence")
    if ai.get("rationale"):
        meta["ai_rationale"] = ai["rationale"]

    fingerprint = content_hash(
        {
            "external_id": base.external_id,
            "doc_type": ai_type.value,
            "title": base.title,
            "body": (base.body or "")[:8000],
            "meta": meta,
            "organized": merged_org,
        }
    )

    return NormalizedDocument(
        external_id=base.external_id,
        doc_type=ai_type,
        source_system=base.source_system,
        title=base.title,
        body=base.body,
        meta=meta,
        organized=merged_org,
        crawl_batch_id=base.crawl_batch_id,
        raw_fingerprint=fingerprint,
        preservation=dict(base.preservation),
    )
