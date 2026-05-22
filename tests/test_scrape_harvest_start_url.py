"""Harvest inicial pode ser URL de lista de erros (LEX_AGENT_SCRAPE_HARVEST_START_URL)."""

from __future__ import annotations

from unittest.mock import patch

from naintegra_lex_agent.scrape_loop import run_scrape_cycle
from naintegra_lex_agent.settings import Settings


def test_playwright_harvest_uses_scrape_harvest_start_url(monkeypatch: object) -> None:
    captured: dict[str, object] = {}

    def fake_harvest(**kw: object) -> tuple[int, int]:
        captured.clear()
        captured.update(kw)
        return 0, 4

    monkeypatch.setattr(
        "naintegra_lex_agent.concurso_study.playwright_capture.cmd_playwright_harvest",
        fake_harvest,
    )

    url = "https://www.qconcursos.com/questoes-de-concursos/questoes?my_questions=wrong&per_page=20"
    s = Settings(
        scrape_loop_mode="playwright_harvest",
        scrape_harvest_start_url=url,
    )
    code, msg, n = run_scrape_cycle(s)
    assert code == 0
    assert n == 4
    assert captured.get("start_url") == url
