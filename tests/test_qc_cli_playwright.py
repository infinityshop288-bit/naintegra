"""Regressão: subcomandos playwright-* não definem --consolidated (main não pode acessar args.consolidated)."""

from __future__ import annotations

import sys

import pytest

from naintegra_lex_agent.concurso_study import cli as cli_mod


def test_main_playwright_save_state_no_consolidated_attr(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_save(**kw: object) -> int:
        called["kw"] = kw
        return 0

    monkeypatch.setattr(
        "naintegra_lex_agent.concurso_study.playwright_capture.cmd_playwright_save_state",
        fake_save,
    )
    monkeypatch.setattr(sys, "argv", ["naintegra-qconcurso-studies", "playwright-save-state"])

    with pytest.raises(SystemExit) as exc:
        cli_mod.main()
    assert exc.value.code == 0
    assert "out_state" in (called.get("kw") or {})
