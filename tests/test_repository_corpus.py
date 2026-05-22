"""Mescla do corpus versionável no clone NaIntegra."""

from __future__ import annotations

import json

from naintegra_lex_agent.repository_corpus import merge_rows_into_repository_corpus


def test_merge_creates_file(tmp_path) -> None:
    dest = tmp_path / "lex_corpus.jsonl"
    rows = [
        {
            "external_id": "a",
            "doc_type": "legislacao",
            "source_system": None,
            "title": "Lei",
            "body": "Art 1",
            "meta": {},
            "organized": {"tribunal": None},
            "crawl_batch_id": None,
            "content_hash": "h1",
        }
    ]
    total, batch = merge_rows_into_repository_corpus(dest, rows)
    assert batch == 1
    assert total == 1
    lines = dest.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0])["external_id"] == "a"


def test_merge_updates_by_external_id(tmp_path) -> None:
    dest = tmp_path / "c.jsonl"
    merge_rows_into_repository_corpus(
        dest,
        [{"external_id": "x", "doc_type": "sumula", "title": "S1", "body": "b", "meta": {}, "organized": {}, "source_system": None, "crawl_batch_id": None, "content_hash": "1"}],
    )
    merge_rows_into_repository_corpus(
        dest,
        [{"external_id": "x", "doc_type": "sumula", "title": "S1-fix", "body": "b2", "meta": {}, "organized": {}, "source_system": None, "crawl_batch_id": None, "content_hash": "2"}],
    )
    lines = dest.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0])["title"] == "S1-fix"
