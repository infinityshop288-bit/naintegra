"""Preview de evolução organize/questions-loop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from naintegra_lex_agent.preview_evolution import (
    completion_note_skip_reason,
    refresh_organize_preview_after_cycle,
    render_evolution_preview_html,
)
from naintegra_lex_agent.settings import Settings


def test_refresh_appends_jsonl_and_writes_html(tmp_path: Path) -> None:
    jsonl = tmp_path / "evo.jsonl"
    html_out = tmp_path / "evo.html"
    settings = Settings(
        preview_evolution_enabled=True,
        preview_evolution_jsonl_path=jsonl,
        preview_evolution_html_path=html_out,
        organized_batch_id="latest",
    )
    rows = [
        {"doc_type": "legislacao", "external_id": "a"},
        {"doc_type": "jurisprudencia", "external_id": "b"},
    ]
    refresh_organize_preview_after_cycle(
        settings,
        loop_name="organize-loop",
        cycle=1,
        rows=rows,
        error=None,
    )
    assert jsonl.is_file()
    line = jsonl.read_text(encoding="utf-8").strip().splitlines()[0]
    rec = json.loads(line)
    assert rec["cycle"] == 1
    assert rec["n_docs"] == 2
    assert rec["by_type"]["legislacao"] == 1
    assert rec["by_type"]["jurisprudencia"] == 1
    assert html_out.is_file()
    text = html_out.read_text(encoding="utf-8")
    assert "EVOLUTION_DATA_PLACEHOLDER" not in text
    assert '"loop":"organize-loop"' in text.replace(" ", "")


def test_render_skips_bad_jsonl_lines(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    jsonl = tmp_path / "evo.jsonl"
    jsonl.write_text('{"cycle":1,"ts":"x","batch_id":"b","n_docs":0,"by_type":{},"error":null}\nnot-json\n', encoding="utf-8")
    html_out = tmp_path / "out.html"
    settings = Settings(
        preview_evolution_enabled=True,
        preview_evolution_jsonl_path=jsonl,
        preview_evolution_html_path=html_out,
    )
    with caplog.at_level("WARNING"):
        render_evolution_preview_html(settings)
    assert html_out.is_file()
    assert any("inválida" in r.message for r in caplog.records)


def test_completion_note_skipped_when_signal_interrupt() -> None:
    s = Settings(preview_open_note_on_exit=True, max_records_per_cycle=500)
    assert completion_note_skip_reason(
        s,
        interrupted_by_signal=True,
        last_cycle_row_count=4,
        last_cycle_failed=False,
        cycles_executed=3,
    ) is not None


def test_completion_note_allowed_when_clean_shutdown_below_cap() -> None:
    s = Settings(preview_open_note_on_exit=True, max_records_per_cycle=500)
    assert (
        completion_note_skip_reason(
            s,
            interrupted_by_signal=False,
            last_cycle_row_count=4,
            last_cycle_failed=False,
            cycles_executed=1,
        )
        is None
    )


def test_completion_note_skipped_at_truncation_cap() -> None:
    s = Settings(preview_open_note_on_exit=True, max_records_per_cycle=500)
    r = completion_note_skip_reason(
        s,
        interrupted_by_signal=False,
        last_cycle_row_count=500,
        last_cycle_failed=False,
        cycles_executed=2,
    )
    assert r is not None
    assert "MAX_RECORDS_PER_CYCLE" in r


def test_completion_note_skipped_on_cycle_failure() -> None:
    s = Settings(preview_open_note_on_exit=True, max_records_per_cycle=500)
    assert completion_note_skip_reason(
        s,
        interrupted_by_signal=False,
        last_cycle_row_count=0,
        last_cycle_failed=True,
        cycles_executed=1,
    ) is not None
