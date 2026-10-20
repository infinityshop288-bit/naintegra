from naintegra_lex_agent.acervo_varredura.enrich import parse_json_object, strip_html
from naintegra_lex_agent.acervo_varredura.scan import summary_key


def test_parse_json_object_fenced():
    raw = '```json\n{"tese":"ok","aplicacao":"uso"}\n```'
    data = parse_json_object(raw)
    assert data is not None
    assert data["tese"] == "ok"


def test_strip_html_entities():
    assert "110/2001" in strip_html("Lei Complementar n&ordm; 110/2001")


def test_summary_key():
    assert (
        summary_key("https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848.htm")
        == "/ccivil_03/decreto-lei/del2848.htm"
    )
