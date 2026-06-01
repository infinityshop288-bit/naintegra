#!/usr/bin/env python3
"""Publica doutrina CP IURIS 2025 no repositório NaIntegra Lex e no Supabase."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from naintegra_lex_agent.lex_publish import publish_lex_rows  # noqa: E402
from naintegra_lex_agent.repository_corpus import merge_rows_into_repository_corpus  # noqa: E402
from naintegra_lex_agent.schemas import content_hash  # noqa: E402
from naintegra_lex_agent.settings import load_settings  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_CORPUS = REPO / "data" / "cp_iuris_2025" / "corpus.jsonl"
DEFAULT_REPO = REPO / "repository" / "lex_corpus.jsonl"
DEFAULT_WEB = REPO / "web" / "lex" / "data" / "doutrina_catalog.json"


def load_corpus(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: JSON inválido ({exc})") from exc
    return rows


def prepare_row(raw: dict[str, Any]) -> dict[str, Any]:
    eid = str(raw.get("external_id") or "").strip()
    if not eid:
        raise ValueError("registro sem external_id")

    meta = dict(raw.get("meta") or {})
    if raw.get("url") and "url" not in meta:
        meta["url"] = raw["url"]
    if raw.get("doc_key") and "doc_key" not in meta:
        meta["doc_key"] = raw["doc_key"]

    organized = dict(raw.get("organized") or {})
    discipline = meta.get("discipline")
    if discipline and not organized.get("materia"):
        organized["materia"] = discipline

    title = raw.get("title")
    body = raw.get("body") or ""
    ch = content_hash({"external_id": eid, "title": str(title or "")[:240], "body": body[:12000]})

    return {
        "external_id": eid,
        "doc_type": "doutrina",
        "source_system": raw.get("source_system") or "cp_iuris",
        "title": title,
        "body": body,
        "meta": meta,
        "organized": organized,
        "crawl_batch_id": meta.get("corpus") or "cp_iuris_2025",
        "content_hash": ch,
    }


def export_web_catalog(rows: list[dict[str, Any]], out_path: Path) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "documents": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Catálogo web: %s documento(s) → %s", len(rows), out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS, help="JSONL de origem (CP IURIS)")
    parser.add_argument("--repository", type=Path, default=DEFAULT_REPO, help="Destino repository/lex_corpus.jsonl")
    parser.add_argument("--web-out", type=Path, default=DEFAULT_WEB, help="Destino web/lex/data/doutrina_catalog.json")
    parser.add_argument("--skip-repository", action="store_true")
    parser.add_argument("--skip-web", action="store_true")
    parser.add_argument("--skip-supabase", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Limita registros (teste)")
    parser.add_argument("--batch-size", type=int, default=None, help="Override LEX_AGENT_BATCH_SIZE")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    corpus_path = args.corpus.expanduser().resolve()
    if not corpus_path.is_file():
        logger.error("Corpus não encontrado: %s", corpus_path)
        return 1

    raw_rows = load_corpus(corpus_path)
    if args.limit is not None:
        raw_rows = raw_rows[: args.limit]
    rows = [prepare_row(r) for r in raw_rows]
    logger.info("Preparados %s registro(s) de doutrina a partir de %s", len(rows), corpus_path)

    if not args.skip_repository:
        total, batch = merge_rows_into_repository_corpus(args.repository.expanduser().resolve(), rows)
        logger.info("Repositório: %s ids únicos (%s neste lote)", total, batch)

    if not args.skip_web:
        export_web_catalog(rows, args.web_out.expanduser().resolve())

    if args.skip_supabase:
        return 0

    settings = load_settings()
    if args.batch_size:
        settings = settings.model_copy(update={"batch_size": max(1, args.batch_size)})
    if not settings.has_supabase_credentials():
        logger.warning(
            "Supabase não configurado (LEX_AGENT_SUPABASE_URL / LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY). "
            "Publicação remota ignorada."
        )
        return 0

    pub_settings = settings.model_copy(update={"publish_ignore_state": True, "dry_run": False})
    try:
        sent = publish_lex_rows(pub_settings, rows)
    except Exception as exc:
        logger.error(
            "Supabase: falha no upsert (%s). Verifique LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY (JWT service_role). "
            "Repositório e catálogo web já foram gravados; reexecute com --skip-repository --skip-web.",
            exc,
        )
        return 0

    logger.info(
        "Supabase: %s/%s registro(s) enviados a %s.%s",
        sent,
        len(rows),
        settings.lex_schema,
        settings.lex_table,
    )
    if sent < len(rows):
        logger.warning("Supabase: upsert parcial — revise credenciais ou permissões.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
