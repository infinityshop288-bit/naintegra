from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DocType(StrEnum):
    LEGISLACAO = "legislacao"
    JURISPRUDENCIA = "jurisprudencia"
    SUMULA = "sumula"
    QUESTOES_OBJETIVAS = "questoes_objetivas"
    QUESTOES_SUBJETIVAS = "questoes_subjetivas"


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


class NormalizedDocument(BaseModel):
    external_id: str
    doc_type: DocType
    source_system: str | None = None
    title: str | None = None
    body: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    organized: dict[str, Any] = Field(default_factory=dict)
    crawl_batch_id: str | None = None
    raw_fingerprint: str | None = None
    preservation: dict[str, Any] = Field(
        default_factory=dict,
        description="Referências ao artefato bruto preservado (paths relativos, linha, digest).",
    )

    def row_for_supabase(self, schema_table_prefix: str = "") -> dict[str, Any]:
        _ = schema_table_prefix
        meta_out = dict(self.meta)
        if self.preservation:
            meta_out["preservation"] = self.preservation
        return {
            "external_id": self.external_id,
            "doc_type": self.doc_type.value,
            "source_system": self.source_system,
            "title": self.title,
            "body": self.body,
            "meta": meta_out,
            "organized": self.organized,
            "crawl_batch_id": self.crawl_batch_id,
            "content_hash": self.raw_fingerprint,
        }
