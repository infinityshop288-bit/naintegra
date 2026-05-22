from naintegra_lex_agent.concurso_study.import_adapters import (
    api_fragment_to_inbox_record,
    extract_inbox_records_from_json_payload,
)


def test_api_row_wrong_gabarito_vs_user() -> None:
    rec = api_fragment_to_inbox_record(
        {
            "id": "qx-01",
            "disciplina": "Const.",
            "enunciado": "Teste?",
            "alternativas": {"A": "x", "B": "y"},
            "gabarito": "b",
            "resposta_usuario": "A",
        },
        emit_if_wrong_unknown=False,
    )
    assert rec is not None
    assert rec.get("acertou") is False
    assert rec["id"] == "qx-01"


def test_ignore_when_acertou_true() -> None:
    assert (
        api_fragment_to_inbox_record(
            {
                "enunciado": "Teste?",
                "alternativas": {"A": "x", "B": "y"},
                "acertou": True,
            },
            emit_if_wrong_unknown=False,
        )
        is None
    )


def test_skip_unknown_wrong_when_flag_false() -> None:
    assert (
        api_fragment_to_inbox_record(
            {
                "enunciado": "?",
                "alternativas": {"A": "1", "B": "2"},
            },
            emit_if_wrong_unknown=False,
        )
        is None
    )


def test_emit_unknown_marks_assumption_key() -> None:
    rec = api_fragment_to_inbox_record(
        {
            "enunciado": "Pergunta curta?",
            "alternativas": {"A": "um", "B": "dois"},
        },
        emit_if_wrong_unknown=True,
    )
    assert rec is not None
    assert rec.get("acertou") is False
    assert rec.get("_assumed_wrong_no_flag") is True


def test_emit_all_with_gabarito_objetiva_acertou_true() -> None:
    """Modo Lex: inclui questão objetiva mesmo quando o usuário acertou na sessão."""

    payload = {
        "item": {
            "id": "z99",
            "disciplina": "Penal",
            "enunciado": "Enunciado suficientemente longo para validação.",
            "alternativas": {"A": "Um", "B": "Dois"},
            "gabarito": "B",
            "acertou": True,
        }
    }
    seen: set[str] = set()
    recs = extract_inbox_records_from_json_payload(
        payload,
        emit_if_wrong_unknown=False,
        harvest_emit_mode="all_with_gabarito",
        dedupe_keys_seen=seen,
        source_url_note="https://www.qconcursos.com/",
    )
    assert len(recs) == 1
    assert recs[0]["doc_type"] == "questoes_objetivas"
    assert recs[0]["gabarito"] == "B"
    assert recs[0]["source_system"] == "qconcurso_network"


def test_emit_flat_keys_and_tecconcursos_source_system() -> None:
    """Payload estilo SPA agregador: ``texto``, alternativas soltas, gabarito índice."""

    payload = {
        "questao": {
            "codigo": "tc-42",
            "texto": "Enunciado suficientemente longo para validação de pipeline.",
            "alternativa_a": "Primeira hipótese.",
            "alternativa_b": "Segunda hipótese.",
            "opcao_correta": 1,
        }
    }
    seen: set[str] = set()
    recs = extract_inbox_records_from_json_payload(
        payload,
        emit_if_wrong_unknown=False,
        harvest_emit_mode="all_with_gabarito",
        dedupe_keys_seen=seen,
        source_url_note="https://www.tecconcursos.com.br/",
    )
    assert len(recs) == 1
    assert recs[0]["gabarito"] == "B"
    assert recs[0]["source_system"] == "tecconcursos_network"
    assert recs[0]["id"] == "tc-42"


def test_emit_all_with_gabarito_discursiva() -> None:
    payload = {
        "disc": {
            "id": "d1",
            "texto_questao": "Explique a improbidade administrativa em detalhes.",
            "resposta_modelo": "Deve citar a Lei 8.429/92 e seus elementos principais aqui.",
        }
    }
    seen: set[str] = set()
    recs = extract_inbox_records_from_json_payload(
        payload,
        emit_if_wrong_unknown=False,
        harvest_emit_mode="all_with_gabarito",
        dedupe_keys_seen=seen,
        source_url_note="https://www.qconcursos.com/",
    )
    assert len(recs) == 1
    assert recs[0]["doc_type"] == "questoes_subjetivas"
    assert "improbidade" in recs[0]["enunciado_questao"]
    assert recs[0]["source_system"] == "qconcurso_network"
