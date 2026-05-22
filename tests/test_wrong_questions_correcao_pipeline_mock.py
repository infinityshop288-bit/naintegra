"""Pipeline local: inbox JSONL (questão errada) → ingest/consolidado → estudo IA (mockada)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from naintegra_lex_agent.concurso_study.cli import cmd_ingest, read_consolidated
from naintegra_lex_agent.concurso_study.settings import QConcursoStudySettings
from naintegra_lex_agent.concurso_study import study_ai


def test_wrong_question_ingest_then_mock_study_writes_study_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    raw = {
        "source": "https://www.qconcursos.com/questoes/test",
        "enunciado": "Sobre cláusula de reserva de plenário, assinale a correta.",
        "alternativas": {"A": "Órgão fracionário pode afastar lei sem declarar inconstitucionalidade.", "B": "Reserva exige colegiado pleno para afastar incidência sem declarar inconstitucionalidade."},
        "gabarito": "B",
        "resposta_usuario": "A",
        "acertou": False,
        "disciplina": "Direito Constitucional",
    }
    (inbox / "wrong_sample.jsonl").write_text(
        json.dumps(raw, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    consolidated = tmp_path / "wrong_consolidated.jsonl"
    assert cmd_ingest(inbox=inbox, glob_pat="*.jsonl", out_path=consolidated, only_hint=False) == 0
    rows = read_consolidated(consolidated)
    assert len(rows) == 1
    assert rows[0].get("stem_key")

    studies_dir = tmp_path / "studies"

    def fake_ai(_settings: QConcursoStudySettings, _prompt: str) -> str:
        return (
            "### 2. Fundamentos legais\n"
            "CF/1988, art. 97 (reserva de plenário) — texto a conferir no Planalto.\n\n"
            "### 5. Conclusão\n"
            "- Memorizar voto em órgão fracionário vs pleno.\n"
        )

    monkeypatch.setattr(study_ai, "call_study_ai", fake_ai)

    settings = QConcursoStudySettings(
        consolidated_path=consolidated,
        studies_dir=studies_dir,
        studies_cache_sqlite=tmp_path / "qc_cache.sqlite",
        study_prompt_profile="cited_solution",
        anthropic_api_key="dummy-not-used",
    )

    n = study_ai.bulk_study(settings, rows, force=True)
    assert n == 1
    outs = list(studies_dir.glob("*.json"))
    assert len(outs) == 1
    doc = json.loads(outs[0].read_text(encoding="utf-8"))
    assert "Fundamentos legais" in doc["markdown"]
    assert doc.get("study_prompt_profile") == "cited_solution"
