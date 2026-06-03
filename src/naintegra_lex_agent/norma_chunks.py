"""Padronização de public.norma_chunks para o NaIntegra Lex (legislação + jurisprudência)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx

from .pt_norma import VERSION as PT_NORMA_VERSION, apply_pt_norma, domain_for_doc_type
from .taxonomy import canonical_tribunal, infer_doc_type, organize_fields

logger = logging.getLogger(__name__)

NORMA_SCHEMA_VERSION = 1
DEFAULT_CHUNK_SIZE = 1800

# Fontes canônicas consumidas pelo front (web/lex/js/config.js).
SOURCE_LEGISLACAO = frozenset({"planalto", "rideel_vademecum"})
SOURCE_JURISPRUDENCIA = frozenset({"trilhante_informativo"})

# Regras de título/seção (espelho de web/lex/js/legis-meta.js).
_LEGIS_URL_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"constituicao\.htm|constituicao/constituicao", re.I), "Constituição e Adm.", "Constituição Federal de 1988"),
    (re.compile(r"l8112|8112cons", re.I), "Constituição e Adm.", "Lei nº 8.112/1990 — Regime Jurídico dos Servidores Públicos"),
    (re.compile(r"l9784", re.I), "Constituição e Adm.", "Lei nº 9.784/1999 — Processo Administrativo Federal"),
    (re.compile(r"l8429", re.I), "Constituição e Adm.", "Lei nº 8.429/1992 — Improbidade Administrativa"),
    (re.compile(r"l9882", re.I), "Constituição e Adm.", "Lei nº 9.882/1999 — ADI, ADC, ADPF e Mandado de Injunção"),
    (re.compile(r"l13300", re.I), "Constituição e Adm.", "Lei nº 13.300/2016 — Mandado de Injunção"),
    (re.compile(r"del2848|decreto-lei/del2848|cod_pen", re.I), "Penal e Processual", "Decreto-Lei nº 2.848/1940 — Código Penal"),
    (re.compile(r"del3689|decreto-lei/del3689", re.I), "Penal e Processual", "Decreto-Lei nº 3.689/1941 — Código de Processo Penal"),
    (re.compile(r"l11340", re.I), "Penal e Processual", "Lei nº 11.340/2006 — Lei Maria da Penha"),
    (re.compile(r"l7210", re.I), "Penal e Processual", "Lei nº 7.210/1984 — Lei de Execução Penal"),
    (re.compile(r"l11343", re.I), "Penal e Processual", "Lei nº 11.343/2006 — Lei de Drogas"),
    (re.compile(r"l8072", re.I), "Penal e Processual", "Lei nº 8.072/1990 — Crimes Hediondos"),
    (re.compile(r"l12830", re.I), "Penal e Processual", "Lei nº 12.830/2013 — Investigação Criminal"),
    (re.compile(r"l10406|2002/l10406", re.I), "Civil e Trabalho", "Lei nº 10.406/2002 — Código Civil"),
    (re.compile(r"del5452|decreto-lei/del5452", re.I), "Civil e Trabalho", "Decreto-Lei nº 5.452/1943 — CLT"),
    (re.compile(r"l8212|8212cons", re.I), "Civil e Trabalho", "Lei nº 8.212/1991 — Custeio da Previdência Social"),
    (re.compile(r"l8078", re.I), "Civil e Trabalho", "Lei nº 8.078/1990 — Código de Defesa do Consumidor"),
    (re.compile(r"l9514", re.I), "Civil e Trabalho", "Lei nº 9.514/1997 — Alienação fiduciária"),
    (re.compile(r"l8249", re.I), "Legislação Especial", "Lei nº 8.249/1991 — Nota do Tesouro Nacional (NTN)"),
    (re.compile(r"l8666", re.I), "Legislação Especial", "Lei nº 8.666/1993 — Licitações e Contratos"),
    (re.compile(r"l9307", re.I), "Legislação Especial", "Lei nº 9.307/1996 — Lei de Arbitragem"),
    (re.compile(r"l6858", re.I), "Legislação Especial", "Lei nº 6.858/1980 — Pagamento a terceiros"),
    (re.compile(r"l9503", re.I), "Legislação Especial", "Lei nº 9.503/1997 — Código de Trânsito Brasileiro"),
    (re.compile(r"l13105", re.I), "Civil e Trabalho", "Lei nº 13.105/2015 — Código de Processo Civil"),
]


def normalize_norma_url(url: str | None) -> str:
    """Normaliza URL para doc_key estável (https, host minúsculo, sem barra/fragmento final)."""
    if not url or not str(url).strip():
        return ""
    raw = str(url).strip()
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    scheme = "https"
    netloc = (parsed.netloc or parsed.path.split("/")[0]).lower()
    path = parsed.path if parsed.netloc else "/" + "/".join(parsed.path.split("/")[1:])
    path = re.sub(r"/+$", "", path) or "/"
    return urlunparse((scheme, netloc, path, "", "", ""))


def normalize_doc_key(url: str | None, source_file: str | None = None) -> str:
    u = normalize_norma_url(url)
    if u:
        return u
    return (source_file or "").strip()


def doc_fingerprint(url: str) -> str:
    return hashlib.sha256(normalize_norma_url(url).encode()).hexdigest()[:12]


def legis_meta_from_url(url: str) -> dict[str, str]:
    for pattern, secao, titulo in _LEGIS_URL_RULES:
        if pattern.search(url or ""):
            return {"secao_lei_seca": secao, "titulo": titulo}
    m = re.search(r"l(\d{4,5})", url or "", re.I)
    if m:
        num = m.group(1)
        return {
            "secao_lei_seca": "Legislação Especial",
            "titulo": f"Lei nº {num[:4]}.{num[4:]}" if len(num) > 4 else f"Lei nº {num}",
        }
    return {}


def tribunal_from_url(url: str | None) -> str | None:
    u = (url or "").lower()
    if "stf-vinculante" in u or "/stf" in u or "temas-stf" in u:
        return "STF"
    if "/stj" in u or "temas-stj" in u:
        return "STJ"
    if "/tst" in u or "temas-tst" in u:
        return "TST"
    if "/tse" in u:
        return "TSE"
    return None


def doc_type_for_source(source: str, url: str | None = None) -> str:
    if source in SOURCE_LEGISLACAO:
        return "legislacao"
    u = (url or "").lower()
    if "sumula" in u:
        return "sumula"
    return "jurisprudencia"


def fix_text_encoding(text: str) -> str:
    """Repara texto Planalto lido como UTF-8 quando era ISO-8859-1."""
    if not text:
        return text
    if "\ufffd" in text or "Ã" in text or re.search(r"Presid.{1,4}ncia", text):
        for enc in ("latin-1", "cp1252"):
            try:
                repaired = text.encode(enc).decode("utf-8")
                if repaired and repaired != text:
                    return repaired
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
    return text


def chunk_text(text: str, size: int = DEFAULT_CHUNK_SIZE) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = text.rfind("\n\n", start, end)
            if cut > start + size // 3:
                end = cut
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


def standard_metadata(
    *,
    source: str,
    url: str,
    source_file: str,
    extra: dict[str, Any] | None = None,
    titulo: str | None = None,
    secao_lei_seca: str | None = None,
) -> dict[str, Any]:
    """Metadados canônicos gravados em norma_chunks.metadata (consumidos pelo Lex web)."""
    url_n = normalize_norma_url(url)
    legis = legis_meta_from_url(url_n)
    doc_type = doc_type_for_source(source, url_n)
    tribunal = tribunal_from_url(url_n)
    base: dict[str, Any] = {
        "norma_schema_version": NORMA_SCHEMA_VERSION,
        "pt_norma_version": PT_NORMA_VERSION,
        "doc_type": doc_type,
        "doc_key": normalize_doc_key(url_n, source_file),
        "titulo": titulo or legis.get("titulo"),
        "secao_lei_seca": secao_lei_seca or legis.get("secao_lei_seca"),
    }
    if tribunal:
        base["tribunal"] = tribunal
    if extra:
        for k, v in extra.items():
            if v is not None and k not in base:
                base[k] = v
    organized = organize_fields(base)
    base.update({k: v for k, v in organized.items() if v is not None})
    if base.get("tribunal"):
        base["tribunal"] = canonical_tribunal(str(base["tribunal"])) or base["tribunal"]
    return {k: v for k, v in base.items() if v is not None}


def normalize_chunk_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normaliza uma linha antes do upsert (url, texto, metadata)."""
    source = str(row.get("source") or "").strip()
    url = normalize_norma_url(str(row.get("url") or ""))
    source_file = str(row.get("source_file") or "").strip()
    text = fix_text_encoding(str(row.get("text") or ""))
    doc_type = doc_type_for_source(source, url)
    text = apply_pt_norma(text, domain=domain_for_doc_type(doc_type, source))
    meta_in = dict(row.get("metadata") or {})
    meta = standard_metadata(
        source=source,
        url=url,
        source_file=source_file,
        extra=meta_in,
        titulo=meta_in.get("titulo"),
        secao_lei_seca=meta_in.get("secao_lei_seca"),
    )
    idx = int(row.get("chunk_index") or 0)
    fp = doc_fingerprint(url)
    row_id = str(row.get("id") or f"{fp}-{idx}")
    if not row.get("id") or not str(row["id"]).startswith(fp):
        row_id = f"{fp}-{idx}"
    return {
        "id": row_id,
        "source": source,
        "source_file": source_file,
        "url": url,
        "chunk_index": idx,
        "text": text,
        "metadata": meta,
    }


def rows_from_document(
    *,
    source: str,
    url: str,
    body: str,
    source_file: str | None = None,
    titulo: str | None = None,
    secao_lei_seca: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    header: str | None = None,
) -> list[dict[str, Any]]:
    url_n = normalize_norma_url(url)
    fp = doc_fingerprint(url_n)
    rel = source_file or f"output_{source}/{fp}.md"
    meta_extra = dict(extra_metadata or {})
    if titulo:
        meta_extra.setdefault("titulo", titulo)
    if secao_lei_seca:
        meta_extra.setdefault("secao_lei_seca", secao_lei_seca)
    full = (header or "") + fix_text_encoding(body.strip())
    doc_type = doc_type_for_source(source, url_n)
    full = apply_pt_norma(full, domain=domain_for_doc_type(doc_type, source))
    if titulo and not header:
        full = f"# {titulo}\n\nFonte: {url_n}\n\n{full}"
    chunks = chunk_text(full, chunk_size)
    out: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        meta = standard_metadata(
            source=source,
            url=url_n,
            source_file=rel,
            extra=meta_extra,
            titulo=titulo,
            secao_lei_seca=secao_lei_seca,
        )
        out.append(
            {
                "id": f"{fp}-{i}",
                "source": source,
                "source_file": rel,
                "url": url_n,
                "chunk_index": i,
                "text": chunk,
                "metadata": meta,
            }
        )
    return out


def rows_from_normalized_document(doc: Any) -> list[dict[str, Any]]:
    """Converte NormalizedDocument (agente) em chunks norma_chunks."""
    source = _map_source_system(getattr(doc, "source_system", None), getattr(doc, "doc_type", None))
    if not source:
        return []
    meta = dict(getattr(doc, "meta", {}) or {})
    organized = dict(getattr(doc, "organized", {}) or {})
    meta.update({k: v for k, v in organized.items() if v is not None})
    url = meta.get("url") or meta.get("source_url") or meta.get("canonical_url") or ""
    if not url and getattr(doc, "external_id", ""):
        url = str(doc.external_id)
    body = getattr(doc, "body", None) or ""
    if not body.strip():
        return []
    return rows_from_document(
        source=source,
        url=str(url),
        body=body,
        titulo=getattr(doc, "title", None),
        secao_lei_seca=meta.get("secao_lei_seca"),
        extra_metadata=meta,
    )


def _map_source_system(source_system: str | None, doc_type: Any) -> str | None:
    ss = (source_system or "").strip().lower()
    if ss in SOURCE_LEGISLACAO | SOURCE_JURISPRUDENCIA:
        return ss
    if ss in ("trilhante", "trilhante_informativo", "informativos"):
        return "trilhante_informativo"
    if ss in ("rideel", "rideel_vademecum", "vademecum"):
        return "rideel_vademecum"
    if ss in ("planalto", "legislacao_planalto"):
        return "planalto"
    dt = getattr(doc_type, "value", doc_type)
    dt_s = str(dt or "").lower()
    inferred = infer_doc_type(dt_s, {})
    if inferred in ("legislacao", "sumula"):
        return "planalto" if ss == "planalto" else "rideel_vademecum"
    if inferred == "jurisprudencia":
        return "trilhante_informativo"
    return None


def supabase_headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def reapply_pt_norma_rows(
    rows: list[dict[str, Any]],
    *,
    only_stale: bool = False,
) -> tuple[list[dict[str, Any]], int, int]:
    """Reaplica português jurídico (pt_norma) antes do upsert.

    Returns:
        (linhas alteradas para upsert, quantidade alterada, quantidade ignorada por only_stale)
    """
    out: list[dict[str, Any]] = []
    changed = 0
    skipped = 0
    for row in rows:
        meta = dict(row.get("metadata") or {})
        if only_stale and meta.get("pt_norma_version") == PT_NORMA_VERSION:
            skipped += 1
            continue
        before = str(row.get("text") or "")
        normalized = normalize_chunk_row(row)
        if normalized["text"] != before or meta.get("pt_norma_version") != PT_NORMA_VERSION:
            changed += 1
            out.append(normalized)
    return out, changed, skipped


def upsert_rows_rpc(
    rows: list[dict[str, Any]],
    *,
    supabase_url: str,
    supabase_key: str,
    batch_size: int = 40,
) -> int:
    if not rows:
        return 0
    normalized = [normalize_chunk_row(r) for r in rows]
    url = supabase_url.rstrip("/")
    headers = supabase_headers(supabase_key)
    total = 0
    with httpx.Client(timeout=180) as client:
        for i in range(0, len(normalized), batch_size):
            batch = normalized[i : i + batch_size]
            r = client.post(
                f"{url}/rest/v1/rpc/upsert_norma_chunks_batch",
                headers=headers,
                json={"payload": batch},
            )
            r.raise_for_status()
            n = r.json()
            total += int(n) if isinstance(n, int) else len(batch)
    return total


def refresh_catalog_mv(*, supabase_url: str, supabase_key: str) -> bool:
    url = supabase_url.rstrip("/")
    headers = supabase_headers(supabase_key)
    try:
        with httpx.Client(timeout=300) as client:
            r = client.post(
                f"{url}/rest/v1/rpc/refresh_norma_document_catalog_mv",
                headers=headers,
                json={},
            )
            r.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("refresh_norma_document_catalog_mv falhou (MV pode estar atualizada): %s", exc)
        return False


def list_catalog_doc_keys(
    *,
    supabase_url: str,
    supabase_key: str,
    source: str,
) -> set[str]:
    headers = supabase_headers(supabase_key)
    keys: set[str] = set()
    offset = 0
    with httpx.Client(timeout=60) as client:
        while True:
            r = client.post(
                f"{supabase_url.rstrip('/')}/rest/v1/rpc/list_norma_document_catalog",
                headers=headers,
                json={"p_source": source, "p_limit": 500, "p_offset": offset},
            )
            r.raise_for_status()
            rows = r.json()
            if not rows:
                break
            for row in rows:
                dk = str(row.get("doc_key") or "")
                keys.add(dk)
                keys.add(normalize_norma_url(dk))
            if len(rows) < 500:
                break
            offset += 500
    return keys
