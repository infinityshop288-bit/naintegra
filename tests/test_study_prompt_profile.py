"""Perfil cited_solution altera wrapper do utilizador (sem chamar API)."""

from __future__ import annotations

from naintegra_lex_agent.concurso_study.settings import QConcursoStudySettings
from naintegra_lex_agent.concurso_study.study_ai import build_user_prompt, study_system_prompt


def test_build_user_prompt_cited_mentions_error_page_context() -> None:
    row = {
        "stem_key": "abc",
        "enunciado": "Assinale a correta.",
        "alternativas": {"A": "Um", "B": "Dois"},
        "_gabarito_letter_hidden": "A",
        "_user_wrong_letter_hidden": "B",
    }
    settings = QConcursoStudySettings(study_prompt_profile="cited_solution")
    body = build_user_prompt(row, settings)
    assert "página de erros" in body
    assert "### 2. Fundamentos legais" in study_system_prompt(settings)


def test_build_user_prompt_exam_prep_sections_hint() -> None:
    row = {
        "stem_key": "abc",
        "enunciado": "Assinale a correta.",
        "alternativas": {"A": "Um", "B": "Dois"},
        "_gabarito_letter_hidden": "A",
        "_user_wrong_letter_hidden": "B",
    }
    settings = QConcursoStudySettings(study_prompt_profile="exam_prep")
    body = build_user_prompt(row, settings)
    assert "secções 1 a 7" in body
    assert "### 1. Regra central do tema" in study_system_prompt(settings)
