"""Consolida legislação/jurisprudência coletada → public.norma_chunks (Lex)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .ai_cache import AIDecisionCache
from .legal_text import pick_display_title, pick_verbatim_body
from .material_merge import merge_material_into_corpus, settings_with_trilhante_informativo_root
from .norma_chunks import (
    doc_fingerprint,
    normalize_doc_key,
    normalize_norma_url,
    refresh_catalog_mv,
    rows_from_document,
    rows_from_normalized_document,
    upsert_rows_rpc,
)
from .norma_format_ai import maybe_format_body
from .pipeline import normalize_record, select_and_normalize
from .schemas import DocType, NormalizedDocument, content_hash
from .settings import Settings
from .state_store import StateStore

logger = logging.getLogger(__name__)

_QUESTION_TYPES = frozenset(
    {"questoes_objetivas", "questoes_subjetivas", "questao_objetiva", "questao_subjetiva"}
)

_URL_KEYS = ("url", "source_url", "canonical_url", "link", "href", "fonte_url")


@dataclass
class ConsolidateStats:
    scanned: int = 0
    skipped_state: int = 0
    skipped_non_normative: int = 0
    skipped_unpublishable: int = 0
    normalized: int = 0
    published_chunks: int = 0
    published_docs: int = 0
    ai_formatted: int = 0
    errors: int = 0


@dataclass
class ConsolidateResult:
    stats: ConsolidateStats = field(default_factory=ConsolidateStats)
    doc_keys: list[str] = field(default_factory=list)


def _iter_jsonl_records(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def _source_from_path(path: Path) -> str | None:
    p = str(path).lower()
    if "trilhante" in p or "informativo" in p:
        return "trilhante_informativo"
    if "rideel" in p or "vademecum" in p:
        return "rideel_vademecum"
    if "planalto" in p or "legislacao" in p:
        return "planalto"
    return None


def _url_from_markdown_path(path: Path, text: str) -> str:
    for key in _URL_KEYS:
        m = re.search(rf"^{re.escape(key)}:\s*(\S+)", text, re.I | re.M)
        if m:
            return normalize_norma_url(m.group(1))
    m = re.search(r"Fonte:\s*(https?://\S+)", text, re.I)
    if m:
        return normalize_norma_url(m.group(1))
    m = re.search(r"(https?://(?:www\.)?planalto\.gov\.br/\S+)", text, re.I)
    if m:
        return normalize_norma_url(m.group(1))
    m = re.search(r"(https?://informativos\.trilhante\.com\.br/\S+)", text, re.I)
    if m:
        return normalize_norma_url(m.group(1).rstrip(").,"))
    name = path.name
    if "planalto.gov.br" in name or "informativos.trilhante" in name:
        slug = name.split("_", 1)[-1].removesuffix(".md")
        slug = slug.replace("_", "/").replace(".com.br", ".com.br/")
        if not slug.startswith("http"):
            slug = "https://" + slug
        return normalize_norma_url(slug)
    return normalize_norma_url(f"file://local/{path.as_posix()}")


def _markdown_to_record(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if len(text.strip()) < 40:
        return None
    url = _url_from_markdown_path(path, text)
    source = _source_from_path(path) or _source_from_path(path.parent) or "rideel_vademecum"
    if "trilhante.com.br" in url:
        source = "trilhante_informativo"
    elif "planalto.gov.br" in url:
        source = "planalto"
    title = None
    for line in text.splitlines()[:12]:
        if line.startswith("# "):
            title = line[2:].strip()
            break
    rel = str(path)
    return {
        "id": doc_fingerprint(url),
        "external_id": doc_fingerprint(url),
        "source": source,
        "source_system": source,
        "url": url,
        "titulo": title,
        "texto": text,
        "metadata": {
            "corpus_root": str(path.parent),
            "relative_path": rel,
            "url": url,
        },
        "_source_file": rel,
    }


def infer_norma_source(record: dict[str, Any]) -> str | None:
    raw = record.get("source") or record.get("source_system") or ""
    s = str(raw).strip().lower()
    mapping = {
        "planalto": "planalto",
        "rideel_vademecum": "rideel_vademecum",
        "rideel": "rideel_vademecum",
        "vademecum": "rideel_vademecum",
        "trilhante_informativo": "trilhante_informativo",
        "trilhante": "trilhante_informativo",
        "informativos": "trilhante_informativo",
    }
    if s in mapping:
        return mapping[s]
    url = str(record.get("url") or record.get("metadata", {}).get("url") or "")
    if "planalto.gov.br" in url:
        return "planalto"
    if "trilhante.com.br" in url:
        return "trilhante_informativo"
    dt = str(record.get("type") or record.get("doc_type") or "").lower()
    if dt in ("jurisprudencia", "sumula"):
        return "trilhante_informativo"
    if dt == "legislacao":
        return "rideel_vademecum"
    path_hint = record.get("_source_file") or record.get("metadata", {}).get("relative_path") or ""
    return _source_from_path(Path(str(path_hint)))


def is_normative_record(record: dict[str, Any]) -> bool:
    dt = str(record.get("type") or record.get("doc_type") or "").lower()
    if dt in _QUESTION_TYPES:
        return False
    if dt.startswith("questao"):
        return False
    body = pick_verbatim_body(record)
    title = pick_display_title(record)
    return bool((body and len(body.strip()) >= 20) or title)


def resolve_document_url(record: dict[str, Any], doc: NormalizedDocument) -> str:
    meta = dict(doc.meta or {})
    for key in _URL_KEYS:
        val = record.get(key) or meta.get(key)
        if val:
            return normalize_norma_url(str(val))
    rel = meta.get("relative_path") or record.get("_source_file") or ""
    if rel:
        return _url_from_markdown_path(Path(str(rel)), doc.body or "")
    return normalize_norma_url(f"https://naintegra.local/lex/{doc.external_id}")


def collect_raw_records(settings: Settings) -> list[dict[str, Any]]:
    if settings.material_merge_before_cycle:
        merge_material_into_corpus(settings)

    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    inbox = settings.crawl_inbox_path.resolve()
    corpus = inbox / settings.corpus_output_name
    if corpus.is_file():
        for rec in _iter_jsonl_records(corpus):
            key = str(rec.get("external_id") or rec.get("id") or json.dumps(rec, sort_keys=True)[:80])
            if key not in seen:
                seen.add(key)
                out.append(rec)

    roots: list[str] = []
    if settings.trilhante_informativo_root:
        roots.append(str(settings.trilhante_informativo_root))
    for part in settings.norma_markdown_roots.split(","):
        part = part.strip()
        if part:
            roots.append(part)
    for part in settings.material_merge_extra_roots.split(","):
        part = part.strip()
        if part and part not in roots:
            roots.append(part)

    for root in roots:
        p = Path(root).expanduser()
        if not p.is_dir():
            continue
        for md in sorted(p.glob("**/*.md")):
            rec = _markdown_to_record(md)
            if not rec:
                continue
            key = rec["external_id"]
            if key in seen:
                continue
            seen.add(key)
            out.append(rec)

    limit = int(settings.max_records_per_cycle)
    return out[:limit] if limit > 0 else out


def is_publishable_url(url: str) -> bool:
    u = normalize_norma_url(url)
    if not u.startswith("https://"):
        return False
    blocked = ("naintegra.local", "file://local")
    return not any(b in u for b in blocked)


def _doc_state_key(source: str, doc_key: str) -> str:
    return f"{source}::{doc_key}"
    return f"{source}::{doc_key}"


def _body_fingerprint(source: str, doc_key: str, body: str) -> str:
    return content_hash({"source": source, "doc_key": doc_key, "body": body[:12000]})


def publish_document_rows(
    settings: Settings,
    *,
    rows: list[dict[str, Any]],
    state: StateStore | None,
    stats: ConsolidateStats,
) -> bool:
    if not rows:
        return False
    source = rows[0]["source"]
    doc_key = normalize_doc_key(rows[0]["url"], rows[0].get("source_file"))
    body_joined = "\n\n".join(r["text"] for r in rows)
    fp = _body_fingerprint(source, doc_key, body_joined)
    state_key = _doc_state_key(source, doc_key)
    if state and state.should_skip(state_key, fp):
        stats.skipped_state += 1
        return False

    if not is_publishable_url(doc_key):
        logger.debug("URL não publicável (pulado): %s", doc_key)
        stats.skipped_unpublishable += 1
        return False

    if settings.dry_run:
        logger.info("[dry-run] publicaria %s chunk(s) → %s", len(rows), state_key)
        stats.published_docs += 1
        stats.published_chunks += len(rows)
        return True

    if not settings.has_supabase_credentials():
        logger.error("Supabase não configurado; defina LEX_AGENT_SUPABASE_URL e chave")
        stats.errors += 1
        return False

    try:
        n = upsert_rows_rpc(
            rows,
            supabase_url=str(settings.supabase_url),
            supabase_key=str(settings.supabase_service_role_key),
        )
    except Exception:
        logger.exception("Falha ao publicar %s", state_key)
        stats.errors += 1
        return False

    stats.published_docs += 1
    stats.published_chunks += n
    if state:
        state.mark(state_key, fp)
    return True


def consolidate_cycle(settings: Settings, state: StateStore | None = None) -> ConsolidateResult:
    stats = ConsolidateStats()
    result = ConsolidateResult(stats=stats)

    raw_records = collect_raw_records(settings)
    stats.scanned = len(raw_records)

    ai_cache: AIDecisionCache | None = None
    if settings.ai_enabled:
        ai_cache = AIDecisionCache(settings.ai_cache_path)

    try:
        for record in raw_records:
            if not is_normative_record(record):
                stats.skipped_non_normative += 1
                continue

            source_hint = infer_norma_source(record)
            if source_hint:
                record.setdefault("source", source_hint)
                record.setdefault("source_system", source_hint)

            docs: list[NormalizedDocument] = []
            if settings.ai_enabled and settings.ai_mode != "off":
                docs = select_and_normalize([record], settings, ai_cache)
            else:
                norm = normalize_record(record, settings, None, [0])
                if norm:
                    docs = [norm]

            if not docs:
                stats.errors += 1
                continue

            stats.normalized += 1
            doc = docs[0]
            url = resolve_document_url(record, doc)
            doc.meta["url"] = url
            body = doc.body or ""
            if settings.norma_ai_format_enabled or settings.norma_ai_format_mode != "off":
                new_body = maybe_format_body(
                    settings,
                    body,
                    doc_type=doc.doc_type.value,
                    title=doc.title,
                )
                if new_body != body:
                    stats.ai_formatted += 1
                    doc = doc.model_copy(update={"body": new_body})

            rows = rows_from_normalized_document(doc)
            if not rows and body.strip():
                meta = dict(doc.meta or {})
                rows = rows_from_document(
                    source=source_hint or "rideel_vademecum",
                    url=url,
                    body=doc.body or body,
                    source_file=meta.get("relative_path"),
                    titulo=doc.title,
                    secao_lei_seca=meta.get("secao_lei_seca"),
                    extra_metadata=meta,
                )

            if publish_document_rows(settings, rows=rows, state=state, stats=stats):
                result.doc_keys.append(normalize_doc_key(url, rows[0].get("source_file")))

    finally:
        if ai_cache is not None:
            ai_cache.close()

    if stats.published_chunks and settings.has_supabase_credentials() and not settings.dry_run:
        refresh_catalog_mv(
            supabase_url=str(settings.supabase_url),
            supabase_key=str(settings.supabase_service_role_key),
        )
        if settings.norma_consolidate_enrich_catalog:
            _rpc_enrich_catalog(settings)

    return result


def _rpc_enrich_catalog(settings: Settings) -> None:
    import httpx

    from .norma_chunks import supabase_headers

    try:
        with httpx.Client(timeout=300) as client:
            r = client.post(
                f"{settings.supabase_url.rstrip('/')}/rest/v1/rpc/enrich_norma_catalog_chunks",
                headers=supabase_headers(str(settings.supabase_service_role_key)),
                json={"p_source": None},
            )
            if r.status_code < 400:
                logger.info("enrich_norma_catalog_chunks: %s", r.json())
    except Exception:
        logger.warning("enrich_norma_catalog_chunks indisponível ou expirou", exc_info=True)
