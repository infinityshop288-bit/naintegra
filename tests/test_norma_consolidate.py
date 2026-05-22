from __future__ import annotations

from naintegra_lex_agent.norma_consolidate import (
    infer_norma_source,
    is_normative_record,
    resolve_document_url,
)
from naintegra_lex_agent.norma_format_ai import needs_ai_format
from naintegra_lex_agent.schemas import DocType, NormalizedDocument


def test_infer_norma_source_planalto():
    rec = {"source": "planalto", "url": "https://www.planalto.gov.br/leis/l8112.htm"}
    assert infer_norma_source(rec) == "planalto"


def test_infer_norma_source_trilhante_from_type():
    rec = {"type": "jurisprudencia", "metadata": {"tribunal": "STJ"}}
    assert infer_norma_source(rec) == "trilhante_informativo"


def test_is_normative_skips_questions():
    assert not is_normative_record({"type": "questoes_objetivas", "texto": "foo"})


def test_is_normative_accepts_legislation():
    assert is_normative_record(
        {"type": "legislacao", "titulo": "Lei X", "dispositivo": "Art. 1º Teste de lei."}
    )


def test_needs_ai_format_detects_crawl_noise():
    body = (
        "Menu principal [buscador](https://informativos.trilhante.com.br/buscador) "
        "texto jurídico com links extras e navegação do site trilhante informativo "
        "que precisa ser limpo antes de publicar no sistema lex para concursos."
    )
    assert needs_ai_format(body)


def test_resolve_document_url_from_record():
    doc = NormalizedDocument(
        external_id="x1",
        doc_type=DocType.LEGISLACAO,
        source_system="planalto",
        title="Lei",
        body="Art. 1º",
        meta={},
    )
    url = resolve_document_url({"url": "http://www.planalto.gov.br/leis/l8429.htm"}, doc)
    assert url.startswith("https://www.planalto.gov.br")
