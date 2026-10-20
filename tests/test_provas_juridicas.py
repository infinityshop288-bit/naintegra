from naintegra_lex_agent.provas_juridicas.careers import career_tags, in_year_window
from naintegra_lex_agent.provas_juridicas.citations import extract_article_block, extract_art_numbers
from naintegra_lex_agent.provas_juridicas.codex_client import extract_output_text, resolve_model
from naintegra_lex_agent.provas_juridicas.loop import merge_new_rows, pending_indices
from naintegra_lex_agent.provas_juridicas.status import summarize


def test_career_tags_juiz():
    row = {
        "meta": {"carreira": "juiz_estadual"},
        "organized": {"ano": 2025, "materia": "Direito Constitucional"},
    }
    assert "juiz" in career_tags(row)
    assert in_year_window(row)


def test_career_tags_old_year_excluded():
    row = {"meta": {"carreira": "juiz_estadual"}, "organized": {"ano": 2022}}
    assert in_year_window(row) is False


def test_extract_art_numbers():
    assert extract_art_numbers("conforme o art. 129 do Código Penal e o art. 5º da CF") == ["129", "5"]


def test_extract_article_block():
    body = (
        "Art. 128. Algo anterior.\n\n"
        "Art. 129. Ofender a integridade corporal ou a saúde de outrem:\n"
        "Pena - detenção, de três meses a um ano.\n\n"
        "Art. 130. Expor alguém a contágio."
    )
    bloco = extract_article_block(body, "129")
    assert bloco is not None
    assert bloco.startswith("Art. 129")
    assert "Art. 130" not in bloco
    falso = (
        "Art. 122. Induzir alguém ao suicídio.\n"
        "aplica-se o art. 129 deste Código:\n\n"
        "Art. 129. Ofender a integridade corporal ou a saúde de outrem:"
    )
    certo = extract_article_block(falso, "129")
    assert certo is not None
    assert certo.startswith("Art. 129")
    assert "Induzir" not in certo


def test_extract_output_text_from_responses_payload():
    payload = {
        "output_text": "",
        "output": [
            {"type": "reasoning", "encrypted_content": "opaque"},
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "### Resposta da IA\nok"}],
            },
        ],
    }
    assert extract_output_text(payload) == "### Resposta da IA\nok"
    assert extract_output_text({"output_text": " direto "}) == "direto"


def test_resolve_model_rejects_unknown():
    assert resolve_model("gpt-5.6-sol") == "gpt-5.6-sol"
    try:
        resolve_model("gpt-4o")
    except ValueError:
        return
    raise AssertionError("modelo desconhecido deveria falhar")


def test_summarize_and_pending():
    rows = [
        {
            "external_id": "pj::a",
            "doc_type": "questoes_subjetivas",
            "carreiras_prova": ["juiz"],
            "meta": {"elaboracao": "ia", "resposta_ia": "ok", "dispositivos": [{}]},
        },
        {
            "external_id": "pj::b",
            "doc_type": "questoes_objetivas",
            "carreiras_prova": ["promotor"],
            "meta": {"elaboracao": "acervo", "resposta_ia": "fallback"},
        },
    ]
    stats = summarize(rows)
    assert stats["catalogo"] == 2
    assert stats["ia"] == 1
    assert stats["acervo"] == 1
    assert stats["subjetivas_ia"] == 1
    assert pending_indices(rows) == [1]


def test_merge_new_rows(tmp_path):
    src = tmp_path / "questoes.json"
    src.write_text(
        '{"documents":[{"external_id":"qb::novo","doc_type":"questoes_objetivas",'
        '"body":"x","meta":{"carreira":"juiz_estadual"},"organized":{"ano":2025}}]}',
        encoding="utf-8",
    )
    rows: list = []
    assert merge_new_rows(rows, src) == 1
    assert merge_new_rows(rows, src) == 0
    assert rows[0]["external_id"].startswith("pj::")
