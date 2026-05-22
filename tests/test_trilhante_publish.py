"""Fusão Trilhante + publicação Lex."""

from __future__ import annotations

from pathlib import Path

import pytest

from naintegra_lex_agent.lex_publish import publish_lex_rows
from naintegra_lex_agent.material_merge import settings_with_trilhante_informativo_root
from naintegra_lex_agent.settings import Settings


def test_settings_with_trilhante_appends_unique_root(tmp_path: Path) -> None:
    tri = tmp_path / "output_trilhante_informativo"
    tri.mkdir()
    s = Settings(
        trilhante_informativo_root=tri,
        material_merge_extra_roots="examples/crawl",
    )
    s2 = settings_with_trilhante_informativo_root(s)
    roots = [x.strip() for x in s2.material_merge_extra_roots.split(",") if x.strip()]
    assert "examples/crawl" in roots
    assert str(tri.resolve()) in roots
    s3 = settings_with_trilhante_informativo_root(s2)
    assert s3.material_merge_extra_roots == s2.material_merge_extra_roots


def test_publish_lex_rows_ignore_state_calls_upsert(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    batches: list[int] = []

    def fake_upsert(rows: list, _settings: Settings) -> bool:
        batches.append(len(rows))
        return True

    monkeypatch.setattr("naintegra_lex_agent.lex_publish.upsert_batches", fake_upsert)

    settings = Settings(
        dry_run=True,
        publish_ignore_state=True,
        state_db_path=tmp_path / "unused.sqlite",
    )
    rows = [
        {"external_id": "x", "content_hash": "1", "doc_type": "legislacao"},
        {"external_id": "y", "content_hash": "2", "doc_type": "sumula"},
    ]
    n = publish_lex_rows(settings, rows)
    assert n == 2
    assert batches == [2]


def test_publish_lex_rows_incremental_skip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    batches: list[int] = []

    def fake_upsert(rows: list, _settings: Settings) -> bool:
        batches.append(len(rows))
        return True

    monkeypatch.setattr("naintegra_lex_agent.lex_publish.upsert_batches", fake_upsert)

    settings = Settings(
        dry_run=False,
        publish_ignore_state=False,
        state_db_path=tmp_path / "st.sqlite",
    )
    row = {"external_id": "only", "content_hash": "abc", "doc_type": "legislacao"}
    assert publish_lex_rows(settings, [row]) == 1
    assert batches == [1]
    assert publish_lex_rows(settings, [row]) == 0
    assert batches == [1]


def test_publish_lex_rows_returns_zero_when_upsert_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_upsert(_rows: list, _settings: Settings) -> bool:
        return False

    monkeypatch.setattr("naintegra_lex_agent.lex_publish.upsert_batches", fake_upsert)

    settings = Settings(
        dry_run=False,
        publish_ignore_state=True,
        state_db_path=tmp_path / "st.sqlite",
    )
    rows = [{"external_id": "x", "content_hash": "1", "doc_type": "legislacao"}]
    assert publish_lex_rows(settings, rows) == 0
