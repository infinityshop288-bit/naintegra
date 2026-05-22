"""Ollama / OpenAI-compatível local no organizer Lex (sem rede)."""

from __future__ import annotations

import pytest

from naintegra_lex_agent import ai_organizer
from naintegra_lex_agent.settings import Settings


def test_settings_resolved_ollama_default_base() -> None:
    s = Settings(ai_provider="ollama", openai_compatible_base_url=None)
    assert s.resolved_openai_compatible_base_url() == "http://127.0.0.1:11434/v1"


def test_settings_resolved_ollama_override() -> None:
    s = Settings(
        ai_provider="ollama",
        openai_compatible_base_url="http://192.168.1.10:11434/v1",
    )
    assert s.resolved_openai_compatible_base_url() == "http://192.168.1.10:11434/v1"


def test_default_ai_model_ollama() -> None:
    assert ai_organizer.default_ai_model("ollama") == "llama3.2"


def test_organizer_system_prompt_local_suffix() -> None:
    s = ai_organizer.organizer_system_prompt(local_openai_compat=True)
    assert "sem markdown" in s.lower()
    assert "JSON" in s


def test_call_organizer_ai_ollama_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_compat(**kwargs: object) -> str:
        sys = str(kwargs.get("system") or "")
        assert "NaIntegra Lex" in sys
        assert "sem markdown" in sys.lower()
        return (
            '{"doc_type":"legislacao","tribunal":null,"materia":null,"banca":null,"ano":null,'
            '"cargo":null,"numero_questao":null,"formato_questao":null,"secao_lei_seca":"Teste",'
            '"tags_incidencia":[],"confidence":0.9,"short_label":null,"rationale":"ok"}'
        )

    monkeypatch.setattr(ai_organizer, "_openai_compatible_chat", fake_compat)

    out = ai_organizer.call_organizer_ai(
        provider="ollama",
        api_key="",
        model="llama3.2",
        record={"titulo": "MP 1", "texto": "Art. 1º ..."},
        external_id="x1",
        timeout=30.0,
        max_input_chars=8000,
        openai_compatible_base_url="http://127.0.0.1:11434/v1",
    )
    assert out is not None
    assert out["doc_type"] == "legislacao"
    assert out["confidence"] == 0.9
