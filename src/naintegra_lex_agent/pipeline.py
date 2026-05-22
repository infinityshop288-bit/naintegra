from __future__ import annotations

import logging
import re
from typing import Any

from .ai_cache import AIDecisionCache
from .ai_organizer import (
    ai_cache_key,
    call_organizer_ai,
    default_ai_model,
    document_from_ai_only,
    merge_ai_enrichment,
    merge_full_ai_preference,
    needs_enrichment,
)
from .exam_questions import enrich_questoes_meta, looks_like_questao, prime_meta_for_doc_inference
from .legal_text import (
    ALL_HOIST_BODY_KEYS,
    EXPLICACAO_KEYS,
    pick_display_title,
    pick_explicacao,
    pick_verbatim_body,
    strip_dispositivo_keys_from_meta,
)
from .schemas import DocType, NormalizedDocument, content_hash
from .settings import Settings
from .taxonomy import infer_doc_type, organize_fields

logger = logging.getLogger(__name__)

# Campos internos do agente / rastreio (não fazem parte do conteúdo coletado).
_RECORD_INTERNAL_KEYS = frozenset(
    {
        "_source_file",
        "_source_line",
        "_source_index",
        "_verbatim_payload_sha256",
        "_verbatim_parent_file_sha256",
        "_preservation_batch",
        "_preservation_file_relpath",
        "_inbox_file_relpath",
        "_source_byte_offset",
    }
)


def preservation_dict(record: dict[str, Any]) -> dict[str, Any]:
    out = {
        "ingestion_batch_id": record.get("_preservation_batch"),
        "preserved_file_relpath": record.get("_preservation_file_relpath"),
        "inbox_file_relpath": record.get("_inbox_file_relpath"),
        "source_line": record.get("_source_line"),
        "source_index": record.get("_source_index"),
        "preserved_line_byte_offset": record.get("_source_byte_offset"),
        "verbatim_payload_sha256": record.get("_verbatim_payload_sha256"),
        "verbatim_parent_file_sha256": record.get("_verbatim_parent_file_sha256"),
    }
    return {k: v for k, v in out.items() if v is not None}


def _strip_internal(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k not in _RECORD_INTERNAL_KEYS}


def pick_external_id(record: dict[str, Any]) -> str | None:
    for key in ("external_id", "id", "urn", "lexml_id", "hash_id", "public_id"):
        val = record.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    titulo = pick_display_title(record)
    body = pick_verbatim_body(record)
    if titulo and body:
        return content_hash({"t": str(titulo)[:200], "b": str(body)[:2000]})
    return None


def pick_doc_type(record: dict[str, Any], meta: dict[str, Any]) -> DocType | None:
    raw = record.get("doc_type") or record.get("type") or record.get("tipo")
    meta_inf = prime_meta_for_doc_inference(meta, record)
    inferred = infer_doc_type(str(raw) if raw else None, meta_inf)
    if inferred == "legislacao":
        return DocType.LEGISLACAO
    if inferred == "jurisprudencia":
        return DocType.JURISPRUDENCIA
    if inferred == "sumula":
        return DocType.SUMULA
    if inferred == "questoes_objetivas":
        return DocType.QUESTOES_OBJETIVAS
    if inferred == "questoes_subjetivas":
        return DocType.QUESTOES_SUBJETIVAS

    vb = pick_verbatim_body(record)
    text_blob = " ".join(
        str(x).lower()
        for x in (
            record.get("titulo"),
            record.get("title"),
            record.get("texto"),
            record.get("body"),
            vb,
            raw,
        )
        if x
    )
    if "súmula" in text_blob or "sumula" in text_blob:
        return DocType.SUMULA
    if looks_like_questao(record):
        inf2 = infer_doc_type(None, meta_inf)
        if inf2 == "questoes_objetivas":
            return DocType.QUESTOES_OBJETIVAS
        if inf2 == "questoes_subjetivas":
            return DocType.QUESTOES_SUBJETIVAS
        if meta_inf.get("alternativas") is not None or meta_inf.get("opcoes") is not None:
            return DocType.QUESTOES_OBJETIVAS
        return DocType.QUESTOES_SUBJETIVAS
    if re.search(r"\bstf\b|\bstj\b|\btst\b|\btse\b", text_blob):
        if "lei n" in text_blob or "mp n" in text_blob or "decreto" in text_blob:
            return DocType.LEGISLACAO
        return DocType.JURISPRUDENCIA
    if "lei" in text_blob or "decreto" in text_blob or "mp " in text_blob:
        return DocType.LEGISLACAO

    logger.debug(
        "Tipo não inferido por heurística (IA pode assumir se habilitada)",
    )
    return None


_BODY_STRUCTURE_KEYS = ALL_HOIST_BODY_KEYS | frozenset(EXPLICACAO_KEYS) | frozenset(
    {"artigos", "articles", "artigos_texto", "integra", "texto_completo"}
)


def build_meta(record: dict[str, Any]) -> dict[str, Any]:
    base = dict(record.get("metadata") or record.get("meta") or {})
    base = strip_dispositivo_keys_from_meta(base)
    reserved = {
        "external_id",
        "id",
        "type",
        "doc_type",
        "titulo",
        "title",
        "texto",
        "body",
        "content",
        "source",
        "source_system",
        "batch_id",
        "crawl_batch_id",
        "metadata",
        "meta",
    } | _BODY_STRUCTURE_KEYS
    for k, v in record.items():
        if k in reserved or k in _RECORD_INTERNAL_KEYS:
            continue
        if k not in base and v is not None:
            base[k] = v
    return base


def build_heuristic_document(
    clean: dict[str, Any],
    meta: dict[str, Any],
    external_id: str,
    doc_type: DocType,
    preservation: dict[str, Any],
) -> NormalizedDocument:
    title = pick_display_title(clean)
    body = pick_verbatim_body(clean)
    source_system = clean.get("source_system") or clean.get("source")
    batch_id = clean.get("crawl_batch_id") or clean.get("batch_id")

    fingerprint = content_hash(
        {
            "external_id": external_id,
            "doc_type": doc_type.value,
            "title": title,
            "body": (body or "")[:8000],
            "meta": meta,
        }
    )

    organized = organize_fields(meta)

    return NormalizedDocument(
        external_id=external_id,
        doc_type=doc_type,
        source_system=str(source_system) if source_system else None,
        title=str(title) if title else None,
        body=str(body) if body else None,
        meta=meta,
        organized=organized,
        crawl_batch_id=str(batch_id) if batch_id else None,
        raw_fingerprint=fingerprint,
        preservation=dict(preservation),
    )


def ai_api_key(settings: Settings) -> str | None:
    if settings.ai_provider == "anthropic":
        return settings.anthropic_api_key
    if settings.ai_provider == "openai":
        return settings.openai_api_key
    if settings.ai_provider in ("openai_compatible", "ollama"):
        return (settings.openai_compatible_api_key or "").strip() or None
    return None


def fetch_ai_decision(
    *,
    record: dict[str, Any],
    external_id: str,
    settings: Settings,
    cache: AIDecisionCache,
    ai_budget: list[int],
    enrich_hint: str | None,
    apply_min_confidence: bool,
) -> tuple[dict[str, Any] | None, bool]:
    key = ai_cache_key(external_id, record)
    hit = cache.get(key)
    if hit:
        return hit, True

    if ai_budget[0] <= 0:
        logger.debug("Orçamento de chamadas IA esgotado neste ciclo")
        return None, False

    if settings.ai_provider in ("openai_compatible", "ollama"):
        base = settings.resolved_openai_compatible_base_url()
        if not base:
            logger.warning(
                "IA habilitada com %s mas LEX_AGENT_OPENAI_COMPATIBLE_BASE_URL está vazio",
                settings.ai_provider,
            )
            return None, False
    elif not ai_api_key(settings):
        logger.warning("IA habilitada mas nenhuma chave configurada para %s", settings.ai_provider)
        return None, False

    api_key = ai_api_key(settings) or ""

    model = (settings.ai_model or "").strip() or default_ai_model(settings.ai_provider)

    oc_base = (
        settings.resolved_openai_compatible_base_url()
        if settings.ai_provider in ("openai_compatible", "ollama")
        else None
    )

    payload = call_organizer_ai(
        provider=settings.ai_provider,
        api_key=api_key,
        model=model,
        record=record,
        external_id=external_id,
        timeout=float(settings.ai_timeout_seconds),
        max_input_chars=int(settings.ai_max_input_chars),
        enrich_hint=enrich_hint,
        openai_compatible_base_url=oc_base,
    )
    if not payload:
        return None, False

    if apply_min_confidence and payload["confidence"] < float(settings.ai_min_confidence):
        logger.info(
            "IA abaixo do limiar de confiança (%.2f < %.2f); ignorando",
            payload["confidence"],
            settings.ai_min_confidence,
        )
        return None, False

    ai_budget[0] -= 1
    cache.set(key, payload)
    return payload, False


def normalize_record(
    record: dict[str, Any],
    settings: Settings,
    cache: AIDecisionCache | None,
    ai_budget: list[int],
) -> NormalizedDocument | None:
    preservation = preservation_dict(record)
    clean = _strip_internal(record)
    meta = build_meta(clean)
    _exp = pick_explicacao(clean)
    if _exp:
        meta = {**meta, "explicacao": _exp}
    external_id = pick_external_id(clean)
    if not external_id:
        logger.warning("Registro sem external_id derivável (ignorado): %s", record.get("_source_file"))
        return None

    title = pick_display_title(clean)
    body = pick_verbatim_body(clean)

    if not (title or body):
        logger.warning("Registro sem título/corpo (ignorado): external_id=%s", external_id)
        return None

    doc_type = pick_doc_type(clean, meta)
    meta = enrich_questoes_meta(meta, clean, doc_type)

    ai_on = bool(settings.ai_enabled and cache is not None and settings.ai_mode != "off")

    if doc_type is None:
        if not ai_on or settings.ai_mode not in ("fallback", "full"):
            return None
        ai_payload, cached = fetch_ai_decision(
            record=clean,
            external_id=external_id,
            settings=settings,
            cache=cache,
            ai_budget=ai_budget,
            enrich_hint=None,
            apply_min_confidence=True,
        )
        if not ai_payload:
            return None
        return document_from_ai_only(
            external_id=external_id,
            ai=ai_payload,
            raw=clean,
            from_cache=cached,
            ai_mode_label=settings.ai_mode,
            preservation=preservation,
        )

    base = build_heuristic_document(clean, meta, external_id, doc_type, preservation)

    if not ai_on or settings.ai_mode == "fallback":
        return base

    if settings.ai_mode == "enrich":
        if not needs_enrichment(base):
            return base
        hint_extra = ""
        if base.doc_type in (DocType.QUESTOES_OBJETIVAS, DocType.QUESTOES_SUBJETIVAS):
            hint_extra = (
                " Este item é questão de prova: preencha banca, ano, materia, numero_questao e formato_questao "
                "quando estiverem explícitos."
            )
        hint = (
            f"Classificação heurística: doc_type={base.doc_type.value}. "
            "Preencha tribunal, materia e secao_lei_seca quando aplicável; "
            "se já estiverem corretos nos metadados, apenas confirme."
            + hint_extra
        )
        ai_payload, cached = fetch_ai_decision(
            record=clean,
            external_id=external_id,
            settings=settings,
            cache=cache,
            ai_budget=ai_budget,
            enrich_hint=hint,
            apply_min_confidence=False,
        )
        if not ai_payload:
            return base
        merged = merge_ai_enrichment(base, ai_payload)
        merged.meta["ai_cached"] = cached
        return merged

    if settings.ai_mode == "full":
        ai_payload, cached = fetch_ai_decision(
            record=clean,
            external_id=external_id,
            settings=settings,
            cache=cache,
            ai_budget=ai_budget,
            enrich_hint=None,
            apply_min_confidence=False,
        )
        if not ai_payload:
            return base
        if ai_payload["confidence"] >= float(settings.ai_full_doc_override_threshold):
            doc = merge_full_ai_preference(base, ai_payload)
        else:
            doc = merge_ai_enrichment(base, ai_payload)
        doc.meta["ai_cached"] = cached
        return doc

    return base


def select_and_normalize(
    records: list[dict[str, Any]],
    settings: Settings,
    cache: AIDecisionCache | None,
) -> list[NormalizedDocument]:
    budget = [int(settings.ai_max_calls_per_cycle)]
    out: list[NormalizedDocument] = []
    for rec in records:
        norm = normalize_record(rec, settings, cache, budget)
        if norm is not None:
            out.append(norm)
    return out
