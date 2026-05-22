from naintegra_lex_agent.concurso_study.normalize import (
    flatten_alternativas,
    is_wrong_question,
    pick_gabarito,
    record_hints_qconcurso_source,
    scatter_alternativas_from_flat_keys,
    stem_key,
)


def test_record_hints_qconcurso_com() -> None:
    assert record_hints_qconcurso_source({"source": "https://www.qconcurso.com/questões"}) is True


def test_record_hints_qconcursos_com() -> None:
    assert record_hints_qconcurso_source({"source": "https://www.qconcursos.com/questoes"}) is True


def test_record_hints_legacy_br_still_matches() -> None:
    assert record_hints_qconcurso_source({"url": "https://www.qconcursos.com.br/foo"}) is True


def test_record_hints_negative() -> None:
    assert (
        record_hints_qconcurso_source({"titulo": "Lei Seca apenas", "enunciado": "..."}) is False
    )


def test_flatten_alternativas_dict() -> None:
    d = {"a": "  um  ", "B": "dois"}
    assert flatten_alternativas(d) == {"A": "um", "B": "dois"}


def test_flatten_alternativas_list() -> None:
    raw = [
        {"letra": "c", "texto": " três"},
    ]
    assert flatten_alternativas(raw) == {"C": "três"}


def test_flatten_alternativas_list_ordem() -> None:
    raw = [{"ordem": 2, "descricao": "Segunda"}]
    assert flatten_alternativas(raw) == {"B": "Segunda"}


def test_scatter_alternativas_from_flat_keys() -> None:
    d = {"alternativa_a": " Um ", "opcao_b": "Dois"}
    assert scatter_alternativas_from_flat_keys(d) == {"A": "Um", "B": "Dois"}


def test_pick_gabarito_nested_dict() -> None:
    assert pick_gabarito({"gabarito": {"letra": "d"}}) == "D"


def test_pick_gabarito_zero_based_index() -> None:
    assert pick_gabarito({"opcao_correta": 1}) == "B"


def test_wrong_via_acertou() -> None:
    assert is_wrong_question({"acertou": False, "resposta_usuario": "Z"}) is True


def test_wrong_via_gabarito() -> None:
    r = {"gabarito": "b", "resposta_usuario": "c"}
    assert is_wrong_question(r) is True


def test_pick_gabarito_from_text() -> None:
    assert pick_gabarito({"gabarito": "Alternativa B correta"}) == "B"


def test_stem_key_stable() -> None:
    alt = {"A": "x"}
    assert stem_key("  TEXTO mesmo \n texto ", alt) == stem_key("texto mesmo texto", alt)


def test_ambiguous_not_wrong_and_not_include() -> None:
    """Sem sinalização de erro nem par gabarito/marcacao → None."""
    assert is_wrong_question({"enunciado": " só isso ", "titulo": "x"}) is None
