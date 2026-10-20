from naintegra_lex_agent.lex_chat.agent import rewrite_command
from naintegra_lex_agent.lex_chat.search import _score, _tokens
from naintegra_lex_agent.lex_chat.skills import parse_skill_md, save_skill, skill_to_md, slugify


def test_rewrite_commands():
    assert "Busque no acervo" in rewrite_command("/pesquisar art 129")
    assert "elabore o documento" in rewrite_command("/elaborar parecer")
    assert "Liste os documentos" in rewrite_command("/docs")


def test_skill_roundtrip(tmp_path, monkeypatch):
    from naintegra_lex_agent.lex_chat import skills as sk

    monkeypatch.setattr(sk, "SKILLS_DIR", tmp_path)
    saved = save_skill("Parecer MP", "parecer do Ministério Público", "Use tese, fundamentos e conclusão objetiva.")
    assert saved["slug"] == "parecer-mp"
    parsed = parse_skill_md(skill_to_md("abc", "desc", "corpo longo o suficiente para gravar"))
    assert parsed["name"] == "abc"
    assert slugify("Tese STF") == "tese-stf"


def test_search_score():
    tokens = _tokens("artigo 37 constituição")
    assert _score("Art. 37 da Constituição Federal", tokens) > 0
