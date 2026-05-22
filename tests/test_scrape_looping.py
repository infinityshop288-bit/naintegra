"""Testes dos loops de scraping (Playwright mockado — CI sem browser real)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from naintegra_lex_agent import exam_boards_loop, questions_loop
from naintegra_lex_agent.exam_scrape import runner as exam_runner
from naintegra_lex_agent.scrape_loop import main_sync as scrape_loop_main
from naintegra_lex_agent.settings import Settings


@pytest.fixture
def loop_settings(tmp_path: Path) -> Settings:
    inbox = tmp_path / "crawl_inbox"
    inbox.mkdir(parents=True)
    return Settings(
        scrape_loop_mode="playwright_harvest",
        scrape_status_path=tmp_path / "scrape_status.json",
        questions_loop_interval_seconds=5,
        exam_boards_loop_interval_seconds=30,
        poll_interval_seconds=5,
        material_merge_before_cycle=False,
        preserve_inbox_files=False,
        write_organized_manifest=False,
        crawl_inbox_path=inbox,
        organized_output_path=tmp_path / "organized",
        raw_preserved_path=tmp_path / "raw",
        exam_scrape_inbox_path=tmp_path / "exam_inbox",
        exam_scrape_state_dir=tmp_path / ".lex_agent",
        exam_scrape_sources="qconcurso",
        exam_scrape_pairs_per_cycle=2,
        exam_scrape_seconds_per_url=5.0,
        scrape_harvest_emit_mode="all_with_gabarito",
        sync_preview_manifest=False,
    )


def test_questions_loop_runs_scrape_and_collect_multiple_iterations(loop_settings: Settings) -> None:
    scrape_calls: list[int] = []
    collect_calls: list[int] = []

    def fake_scrape(s: Settings) -> tuple[int, str, int]:
        scrape_calls.append(1)
        return 0, "mock ok", 3

    def fake_collect(s: Settings) -> list[dict]:
        collect_calls.append(1)
        return []

    # False = timeout (continua); True = stop após esse ciclo → exatamente 2 iterações.
    wait_returns = [False, True]

    class FakeEvent(threading.Event):
        def wait(self, timeout: float | None = None) -> bool:
            if not wait_returns:
                return True
            return bool(wait_returns.pop(0))

    with patch.object(questions_loop, "load_settings", return_value=loop_settings):
        with patch.object(questions_loop, "run_scrape_cycle", side_effect=fake_scrape):
            with patch.object(questions_loop, "collect_cycle", side_effect=fake_collect):
                with patch.object(questions_loop, "write_scrape_status"):
                    with patch.object(questions_loop.threading, "Event", FakeEvent):
                        with patch.object(questions_loop.sys, "exit") as exit_mock:
                            questions_loop.main_sync()
                            exit_mock.assert_called_once_with(0)

    assert len(scrape_calls) == 2
    assert len(collect_calls) == 2


def test_questions_loop_skips_scrape_when_mode_off(loop_settings: Settings) -> None:
    s = loop_settings.model_copy(update={"scrape_loop_mode": "off"})
    scrape_calls: list[int] = []

    def fake_scrape(*_: object, **__: object) -> tuple[int, str, int]:
        scrape_calls.append(1)
        return 0, "no", 0

    wait_returns = [False, True]

    class FakeEvent(threading.Event):
        def wait(self, timeout: float | None = None) -> bool:
            return bool(wait_returns.pop(0))

    with patch.object(questions_loop, "load_settings", return_value=s):
        with patch.object(questions_loop, "run_scrape_cycle", side_effect=fake_scrape):
            with patch.object(questions_loop, "collect_cycle", return_value=[]):
                with patch.object(questions_loop, "write_scrape_status"):
                    with patch.object(questions_loop.threading, "Event", FakeEvent):
                        with patch.object(questions_loop.sys, "exit"):
                            questions_loop.main_sync()

    assert scrape_calls == []


def test_questions_loop_run_once_single_cycle(loop_settings: Settings) -> None:
    s = loop_settings.model_copy(update={"questions_loop_run_once": True})
    scrape_calls: list[int] = []

    def fake_scrape(_st: Settings) -> tuple[int, str, int]:
        scrape_calls.append(1)
        return 0, "mock ok", 2

    class BoomWait(threading.Event):
        def wait(self, timeout: float | None = None) -> bool:
            raise AssertionError("run_once não deve esperar intervalo entre ciclos")

    with patch.object(questions_loop, "load_settings", return_value=s):
        with patch.object(questions_loop, "run_scrape_cycle", side_effect=fake_scrape):
            with patch.object(questions_loop, "collect_cycle", return_value=[]):
                with patch.object(questions_loop, "write_scrape_status"):
                    with patch.object(questions_loop.threading, "Event", BoomWait):
                        with patch.object(questions_loop.sys, "exit") as exit_mock:
                            questions_loop.main_sync()
                            exit_mock.assert_called_once_with(0)

    assert len(scrape_calls) == 1


def test_exam_boards_loop_invokes_batch_until_stop(loop_settings: Settings) -> None:
    batches: list[int] = []
    wait_returns = [False, True]

    class FakeEvent(threading.Event):
        def wait(self, timeout: float | None = None) -> bool:
            if not wait_returns:
                return True
            return bool(wait_returns.pop(0))

    def fake_batch(_settings: Settings) -> tuple[int, int]:
        batches.append(1)
        return 0, 7

    with patch.object(exam_boards_loop, "load_settings", return_value=loop_settings):
        with patch.object(exam_boards_loop, "run_exam_board_scrape_batch", side_effect=fake_batch):
            with patch.object(exam_boards_loop.threading, "Event", FakeEvent):
                with patch.object(exam_boards_loop.sys, "exit") as exit_mock:
                    exam_boards_loop.main_sync()
                    exit_mock.assert_called_once_with(0)

    assert len(batches) == 2


def test_run_exam_board_scrape_batch_partition_sink_with_mock_playwright(
    loop_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simula ``cmd_playwright_harvest_url_plan`` gravando linhas como após captura JSON."""

    inbox = tmp_path / "exam_partition"
    st = loop_settings.model_copy(
        update={
            "exam_scrape_inbox_path": inbox,
            "exam_scrape_state_dir": tmp_path / ".lex_state",
        }
    )

    def fake_harvest_url_plan(
        *,
        url_tag_pairs: list,
        partition_sink,
        **_: object,
    ) -> tuple[int, int]:
        assert len(url_tag_pairs) >= 1
        _, tags = url_tag_pairs[0]
        assert tags.get("banca") == "FGV"
        partition_sink(
            [
                {
                    "doc_type": "questoes_objetivas",
                    "id": "mock-q-1",
                    "banca": tags["banca"],
                    "cargo_alvo": tags["cargo_alvo"],
                    "gabarito": "A",
                    "texto_questao": "Enunciado synthetic.",
                    "alternativas": [{"letra": "A", "texto": "Ok"}, {"letra": "B", "texto": "No"}],
                }
            ]
        )
        return 0, 1

    monkeypatch.setattr(exam_runner, "cmd_playwright_harvest_url_plan", fake_harvest_url_plan)

    code, n = exam_runner.run_exam_board_scrape_batch(st)
    assert code == 0
    assert n == 1

    part_files = list(inbox.glob("FGV/*.jsonl"))
    assert len(part_files) == 1
    line = part_files[0].read_text(encoding="utf-8").strip()
    row = json.loads(line)
    assert row["gabarito"] == "A"
    assert row["cargo_alvo"]


def test_scrape_loop_single_iteration_mock(loop_settings: Settings) -> None:
    calls: list[int] = []

    def fake_run(settings: Settings) -> tuple[int, str, int]:
        calls.append(1)
        assert settings.scrape_loop_mode == "playwright_harvest"
        return 0, "ok", 5

    wait_returns = [True]

    class FakeEvent(threading.Event):
        def wait(self, timeout: float | None = None) -> bool:
            return bool(wait_returns.pop(0))

    s = loop_settings.model_copy(update={"scrape_loop_interval_seconds": 5})

    with patch("naintegra_lex_agent.scrape_loop.load_settings", return_value=s):
        with patch("naintegra_lex_agent.scrape_loop.run_scrape_cycle", side_effect=fake_run):
            with patch("naintegra_lex_agent.scrape_loop.write_scrape_status"):
                with patch("naintegra_lex_agent.scrape_loop.threading.Event", FakeEvent):
                    with patch("naintegra_lex_agent.scrape_loop.sys.exit") as exit_mock:
                        scrape_loop_main()
                        exit_mock.assert_called_once_with(0)

    assert calls == [1]
