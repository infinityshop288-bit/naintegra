"""Documentos elaborados no chat."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from naintegra_lex_agent.provas_juridicas.status import write_json_atomic

ROOT = Path(__file__).resolve().parents[3]
DOCS_DIR = ROOT / "data" / "lex_chat" / "documentos"
INDEX = ROOT / "web" / "lex" / "data" / "chat_documentos.json"
_SLUG = re.compile(r"[^a-z0-9]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_documents(limit: int = 40) -> list[dict[str, Any]]:
    if not INDEX.is_file():
        return []
    raw = json.loads(INDEX.read_text(encoding="utf-8"))
    docs = list(raw.get("documents") or [])
    return docs[:limit]


def save_document(*, title: str, kind: str, markdown: str, skill: str = "") -> dict[str, Any]:
    title = (title or "Documento").strip()[:180]
    body = (markdown or "").strip()
    if len(body) < 20:
        raise ValueError("documento vazio")
    slug = _SLUG.sub("-", title.lower()).strip("-")[:60] or "documento"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    doc_id = f"{stamp}-{slug}"
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    path = DOCS_DIR / f"{doc_id}.md"
    path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    rec = {
        "id": doc_id,
        "title": title,
        "kind": (kind or "outro").strip()[:40],
        "skill": skill,
        "path": str(path.relative_to(ROOT)),
        "created_at": _now(),
        "preview": body[:280],
    }
    docs = list_documents(200)
    docs.insert(0, rec)
    write_json_atomic(INDEX, {"generated_at": _now(), "count": len(docs), "documents": docs[:200]})
    return rec
