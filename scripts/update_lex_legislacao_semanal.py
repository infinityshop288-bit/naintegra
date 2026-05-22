#!/usr/bin/env python3
"""Atualiza legislação Planalto no Supabase (semanal ou sob demanda).

Detecta alterações por hash do texto compilado (inclui ~~revogado~~ e notas de redação)
e re-ingere apenas documentos modificados.

Uso:
  set -a && source .env && set +a
  python3 scripts/update_lex_legislacao_semanal.py
  python3 scripts/update_lex_legislacao_semanal.py --force
  python3 scripts/update_lex_legislacao_semanal.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from naintegra_lex_agent.norma_chunks import (  # noqa: E402
    list_catalog_doc_keys,
    normalize_norma_url,
    refresh_catalog_mv,
    rows_from_document,
    supabase_headers,
    upsert_rows_rpc,
)
from naintegra_lex_agent.planalto_legis import (  # noqa: E402
    discovered_catalog_rows,
    fetch_planalto_text,
    merge_catalog,
)

SOURCE = "planalto"
STATE_PATH = ROOT / "data" / "legis_update_state.json"
MIN_TEXT_LEN = 200


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"documents": {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"documents": {}}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


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


def list_catalog_rows(sb_url: str, key: str) -> list[dict[str, Any]]:
    headers = supabase_headers(key)
    rows: list[dict[str, Any]] = []
    offset = 0
    with httpx.Client(timeout=60) as client:
        while True:
            r = client.post(
                f"{sb_url.rstrip('/')}/rest/v1/rpc/list_norma_document_catalog",
                headers=headers,
                json={"p_source": SOURCE, "p_limit": 500, "p_offset": offset},
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


def export_legis_summaries() -> None:
    script = ROOT / "scripts" / "export_lex_legis_summaries.js"
    if not script.exists():
        return
    try:
        subprocess.run(["node", str(script)], cwd=ROOT, check=True, timeout=600)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"[WARN] export_lex_legis_summaries.js: {exc}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Atualização semanal da legislação Planalto")
    parser.add_argument("--force", action="store_true", help="Re-ingere todas as leis do catálogo")
    parser.add_argument("--dry-run", action="store_true", help="Só verifica alterações, sem gravar")
    parser.add_argument("--no-export", action="store_true", help="Não regenera legis_summaries.json")
    parser.add_argument("--url", action="append", help="Atualiza apenas URL(s) informada(s)")
    args = parser.parse_args()

    sb_url = os.environ.get("LEX_AGENT_SUPABASE_URL", "").strip()
    key = os.environ.get("LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not sb_url or not key:
        print("[ERRO] Defina LEX_AGENT_SUPABASE_URL e LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY.", file=sys.stderr)
        return 1

    state = load_state()
    docs_state: dict[str, Any] = dict(state.get("documents") or {})

    discovered = discovered_catalog_rows(list_catalog_rows(sb_url, key))
    catalog = merge_catalog(*discovered)

    if args.url:
        wanted = {normalize_norma_url(u) for u in args.url}
        catalog = [law for law in catalog if normalize_norma_url(law["url"]) in wanted]
        if not catalog:
            print("[ERRO] Nenhuma URL do catálogo corresponde a --url", file=sys.stderr)
            return 1

    have = list_catalog_doc_keys(supabase_url=sb_url, supabase_key=key, source=SOURCE)
    updated = 0
    skipped = 0
    errors: list[str] = []
    total_rows = 0

    for law in catalog:
        url = law["url"]
        doc_key = normalize_norma_url(url)
        titulo = law["titulo"]
        print(f"[CHECK] {titulo}")

        try:
            fetched = fetch_planalto_text(url)
        except Exception as exc:
            msg = f"{titulo}: fetch falhou — {exc}"
            errors.append(msg)
            print(f"[WARN] {msg}", file=sys.stderr)
            continue

        if fetched.char_count < MIN_TEXT_LEN:
            msg = f"{titulo}: texto curto ({fetched.char_count} chars)"
            errors.append(msg)
            print(f"[WARN] {msg}", file=sys.stderr)
            continue

        prev = docs_state.get(doc_key, {})
        prev_hash = prev.get("content_hash")
        changed = args.force or prev_hash != fetched.content_hash or doc_key not in have

        if not changed:
            skipped += 1
            docs_state[doc_key] = {
                **prev,
                "titulo": titulo,
                "last_checked": utc_now(),
                "content_hash": fetched.content_hash,
                "char_count": fetched.char_count,
            }
            print(f"  sem alteração ({fetched.char_count} chars)")
            continue

        reason = "forçado" if args.force else ("novo" if doc_key not in have else "modificado")
        print(f"  {reason} — {fetched.char_count} chars (hash {fetched.content_hash[:12]}…)")

        if args.dry_run:
            updated += 1
            continue

        if doc_key in have:
            n_del = delete_document_chunks(sb_url, key, url)
            if n_del:
                print(f"  [DEL] {n_del} chunk(s) antigos")

        rows = rows_from_document(
            source=SOURCE,
            url=url,
            body=fetched.text,
            titulo=titulo,
            secao_lei_seca=law["secao"],
            extra_metadata={
                "corpus": "legislacao_planalto_weekly",
                "content_hash": fetched.content_hash,
                "fetched_at": utc_now(),
            },
        )
        n = upsert_rows_rpc(rows, supabase_url=sb_url, supabase_key=key)
        total_rows += n
        updated += 1
        docs_state[doc_key] = {
            "titulo": titulo,
            "content_hash": fetched.content_hash,
            "char_count": fetched.char_count,
            "last_checked": utc_now(),
            "last_updated": utc_now(),
            "chunks": n,
        }
        print(f"  [OK] {n} chunk(s)")

    if not args.dry_run and total_rows:
        refresh_catalog_mv(supabase_url=sb_url, supabase_key=key)
        if not args.no_export:
            export_legis_summaries()

    state["last_run"] = utc_now()
    state["documents"] = docs_state
    state["stats"] = {
        "checked": len(catalog),
        "updated": updated,
        "skipped": skipped,
        "errors": len(errors),
        "chunks_upserted": total_rows,
    }
    if not args.dry_run:
        save_state(state)

    print(
        f"\nConcluído: {updated} atualizada(s), {skipped} inalterada(s), "
        f"{total_rows} chunk(s), {len(errors)} erro(s)."
    )
    if errors:
        for e in errors[:8]:
            print(f"  - {e}", file=sys.stderr)
    return 0 if updated or skipped else (1 if errors else 0)


if __name__ == "__main__":
    raise SystemExit(main())
