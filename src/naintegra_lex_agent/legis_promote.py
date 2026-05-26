"""Promoção/remoção de legislação Planalto em ``public.norma_chunks`` (Lex web/apps)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from .lexml_impact import should_remove_entire_law
from .norma_chunks import (
    list_catalog_doc_keys,
    normalize_norma_url,
    refresh_catalog_mv,
    rows_from_document,
    supabase_headers,
    upsert_rows_rpc,
)
from .planalto_legis import fetch_planalto_text

SOURCE = "planalto"
MIN_TEXT_LEN = 200


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PromoteResult:
    url: str
    titulo: str
    action: str
    chunks: int = 0
    deleted: int = 0
    message: str = ""


def delete_document_chunks(sb_url: str, key: str, law_url: str) -> int:
    doc_url = normalize_norma_url(law_url)
    urls = {doc_url, doc_url.replace("https://", "http://"), law_url.strip()}
    headers = {**supabase_headers(key), "Prefer": "return=representation"}
    deleted = 0
    with httpx.Client(timeout=180) as client:
        for u in urls:
            if not u:
                continue
            r = client.delete(
                f"{sb_url.rstrip('/')}/rest/v1/norma_chunks?source=eq.planalto&url=eq.{quote(u, safe='')}",
                headers=headers,
            )
            if r.status_code >= 400:
                continue
            if r.text:
                try:
                    deleted += len(r.json())
                except Exception:
                    pass
    return deleted


def list_catalog_rows(sb_url: str, key: str, *, source: str = SOURCE) -> list[dict[str, Any]]:
    headers = supabase_headers(key)
    rows: list[dict[str, Any]] = []
    offset = 0
    with httpx.Client(timeout=60) as client:
        while True:
            r = client.post(
                f"{sb_url.rstrip('/')}/rest/v1/rpc/list_norma_document_catalog",
                headers=headers,
                json={"p_source": source, "p_limit": 500, "p_offset": offset},
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < 500:
                break
            offset += 500
    return rows


def export_legis_summaries(root: Path | None = None) -> None:
    base = root or Path(__file__).resolve().parents[2]
    script = base / "scripts" / "export_lex_legis_summaries.js"
    if not script.exists():
        return
    try:
        subprocess.run(["node", str(script)], cwd=base, check=True, timeout=600)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"[WARN] export_lex_legis_summaries.js: {exc}", file=sys.stderr)


def export_legis_offline_bundle(root: Path | None = None) -> None:
    base = root or Path(__file__).resolve().parents[2]
    script = base / "scripts" / "export_lex_legis_offline.py"
    if not script.exists():
        return
    try:
        subprocess.run([sys.executable, str(script)], cwd=base, check=True, timeout=3600)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"[WARN] export_lex_legis_offline.py: {exc}", file=sys.stderr)


def refresh_law_from_planalto(
    *,
    sb_url: str,
    key: str,
    law: dict[str, str],
    force: bool = False,
    dry_run: bool = False,
    have: set[str] | None = None,
    docs_state: dict[str, Any] | None = None,
    corpus_tag: str = "legislacao_planalto_weekly",
) -> PromoteResult:
    url = law["url"]
    titulo = law["titulo"]
    doc_key = normalize_norma_url(url)
    known = have if have is not None else list_catalog_doc_keys(
        supabase_url=sb_url, supabase_key=key, source=SOURCE
    )

    try:
        fetched = fetch_planalto_text(url)
    except Exception as exc:
        return PromoteResult(url=url, titulo=titulo, action="error", message=str(exc))

    if fetched.char_count < MIN_TEXT_LEN:
        return PromoteResult(
            url=url,
            titulo=titulo,
            action="error",
            message=f"texto curto ({fetched.char_count} chars)",
        )

    prev = (docs_state or {}).get(doc_key, {})
    prev_hash = prev.get("content_hash")
    changed = force or prev_hash != fetched.content_hash or doc_key not in known

    if not changed:
        if docs_state is not None:
            docs_state[doc_key] = {
                **prev,
                "titulo": titulo,
                "last_checked": utc_now(),
                "content_hash": fetched.content_hash,
                "char_count": fetched.char_count,
            }
        return PromoteResult(url=url, titulo=titulo, action="skipped", message="sem alteração")

    if dry_run:
        return PromoteResult(
            url=url,
            titulo=titulo,
            action="would_update",
            message=f"{fetched.char_count} chars",
        )

    deleted = 0
    if doc_key in known:
        deleted = delete_document_chunks(sb_url, key, url)

    rows = rows_from_document(
        source=SOURCE,
        url=url,
        body=fetched.text,
        titulo=titulo,
        secao_lei_seca=law["secao"],
        extra_metadata={
            "corpus": corpus_tag,
            "content_hash": fetched.content_hash,
            "fetched_at": utc_now(),
        },
    )
    n = upsert_rows_rpc(rows, supabase_url=sb_url, supabase_key=key)
    if docs_state is not None:
        docs_state[doc_key] = {
            "titulo": titulo,
            "content_hash": fetched.content_hash,
            "char_count": fetched.char_count,
            "last_checked": utc_now(),
            "last_updated": utc_now(),
            "chunks": n,
        }
    return PromoteResult(
        url=url,
        titulo=titulo,
        action="updated",
        chunks=n,
        deleted=deleted,
        message=f"{fetched.char_count} chars",
    )


def remove_law_from_platform(
    *,
    sb_url: str,
    key: str,
    law: dict[str, str],
    dry_run: bool = False,
    docs_state: dict[str, Any] | None = None,
) -> PromoteResult:
    url = law["url"]
    titulo = law["titulo"]
    doc_key = normalize_norma_url(url)

    if dry_run:
        return PromoteResult(url=url, titulo=titulo, action="would_remove", message="revogação total")

    deleted = delete_document_chunks(sb_url, key, url)
    if docs_state is not None:
        docs_state.pop(doc_key, None)
        docs_state[f"removed::{doc_key}"] = {
            "titulo": titulo,
            "removed_at": utc_now(),
            "reason": "revogacao_total",
        }
    return PromoteResult(
        url=url,
        titulo=titulo,
        action="removed",
        deleted=deleted,
        message="revogação total",
    )


def promote_or_remove_law(
    *,
    sb_url: str,
    key: str,
    law: dict[str, str],
    force: bool = False,
    dry_run: bool = False,
    have: set[str] | None = None,
    docs_state: dict[str, Any] | None = None,
    corpus_tag: str = "legislacao_planalto_weekly",
) -> PromoteResult:
    """Busca Planalto, remove se revogada integralmente; senão upsert formatado Lex."""
    url = law["url"]
    titulo = law["titulo"]
    try:
        fetched = fetch_planalto_text(url)
    except Exception as exc:
        return PromoteResult(url=url, titulo=titulo, action="error", message=str(exc))

    if should_remove_entire_law(title=titulo, body=fetched.text):
        return remove_law_from_platform(
            sb_url=sb_url,
            key=key,
            law=law,
            dry_run=dry_run,
            docs_state=docs_state,
        )

    return refresh_law_from_planalto(
        sb_url=sb_url,
        key=key,
        law=law,
        force=force,
        dry_run=dry_run,
        have=have,
        docs_state=docs_state,
        corpus_tag=corpus_tag,
    )


def supabase_credentials_from_env() -> tuple[str, str]:
    sb_url = os.environ.get("LEX_AGENT_SUPABASE_URL", "").strip()
    key = os.environ.get("LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    return sb_url, key


def load_json_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"documents": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"documents": {}}


def save_json_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
