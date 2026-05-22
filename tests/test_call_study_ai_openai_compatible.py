"""Roteamento call_study_ai → servidor OpenAI-compatível (sem rede)."""

from __future__ import annotations

import pytest

from naintegra_lex_agent.concurso_study.settings import QConcursoStudySettings
from naintegra_lex_agent.concurso_study import study_ai


def test_call_study_ai_openai_compatible_calls_chat_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake(**kwargs: object) -> str:
        captured.update(kwargs)
        return "fake-markdown"

    monkeypatch.setattr(study_ai, "_openai_compatible_chat", fake)

    settings = QConcursoStudySettings(
        ai_provider="openai_compatible",
        openai_compatible_base_url="http://127.0.0.1:11434/v1",
        openai_compatible_api_key="x",
        ai_model="llama3.2",
    )
    assert study_ai.call_study_ai(settings, "user text") == "fake-markdown"
    assert captured["base_url"] == "http://127.0.0.1:11434/v1"
    assert captured["model"] == "llama3.2"
    assert captured["user_prompt"] == "user text"


def test_call_study_ai_openai_compatible_requires_base_url() -> None:
    settings = QConcursoStudySettings(
        ai_provider="openai_compatible",
        openai_compatible_base_url=None,
    )
    with pytest.raises(RuntimeError, match="QC_STUDY_OPENAI_COMPATIBLE_BASE_URL"):
        study_ai.call_study_ai(settings, "x")


def test_call_study_ai_ollama_uses_default_base(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake(**kwargs: object) -> str:
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(study_ai, "_openai_compatible_chat", fake)

    settings = QConcursoStudySettings(ai_provider="ollama", openai_compatible_base_url=None)
    assert study_ai.call_study_ai(settings, "prompt") == "ok"
    assert captured["base_url"] == "http://127.0.0.1:11434/v1"
