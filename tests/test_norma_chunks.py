from __future__ import annotations

from naintegra_lex_agent.norma_chunks import (
    doc_fingerprint,
    doc_type_for_source,
    fix_text_encoding,
    legis_meta_from_url,
    normalize_chunk_row,
    normalize_doc_key,
    normalize_norma_url,
    rows_from_document,
    tribunal_from_url,
)


def test_normalize_norma_url_http_to_https():
    u = "http://WWW.Planalto.gov.br/ccivil_03/leis/l8666cons.htm/"
    assert normalize_norma_url(u) == "https://www.planalto.gov.br/ccivil_03/leis/l8666cons.htm"


def test_doc_key_stable_across_schemes():
    a = normalize_doc_key("http://www.planalto.gov.br/ccivil_03/leis/l8078.htm")
    b = normalize_doc_key("https://www.planalto.gov.br/ccivil_03/leis/l8078.htm")
    assert a == b


def test_doc_fingerprint_uses_normalized_url():
    a = doc_fingerprint("http://www.planalto.gov.br/ccivil_03/decreto-lei/del2848.htm")
    b = doc_fingerprint("https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848.htm")
    assert a == b


def test_legis_meta_cp():
    meta = legis_meta_from_url("https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848.htm")
    assert meta["secao_lei_seca"] == "Penal e Processual"
    assert "Código Penal" in meta["titulo"]


def test_legis_meta_maria_da_penha():
    meta = legis_meta_from_url("https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11340.htm")
    assert meta["secao_lei_seca"] == "Penal e Processual"
    assert "Maria da Penha" in meta["titulo"]


def test_legis_meta_lep():
    meta = legis_meta_from_url("https://www.planalto.gov.br/ccivil_03/leis/l7210.htm")
    assert meta["secao_lei_seca"] == "Penal e Processual"
    assert "Execução Penal" in meta["titulo"]


def test_tribunal_from_trilhante_url():
    assert tribunal_from_url("https://informativos.trilhante.com.br/temas-stf/foo") == "STF"
    assert tribunal_from_url("https://informativos.trilhante.com.br/sumulas/stj") == "STJ"


def test_doc_type_by_source():
    assert doc_type_for_source("planalto", "") == "legislacao"
    assert doc_type_for_source("trilhante_informativo", "https://x/sumulas/stf") == "sumula"


def test_rows_from_document_metadata():
    rows = rows_from_document(
        source="planalto",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
        body="Art. 1º Texto de teste.",
        titulo="Lei nº 8.429/1992",
        secao_lei_seca="Constituição e Adm.",
    )
    assert len(rows) == 1
    assert rows[0]["url"].startswith("https://")
    assert rows[0]["metadata"]["doc_type"] == "legislacao"
    assert rows[0]["metadata"]["norma_schema_version"] == 1
    assert rows[0]["metadata"]["secao_lei_seca"] == "Constituição e Adm."


def test_normalize_chunk_row_rewrites_id_on_url_change():
    row = {
        "id": "oldid-0",
        "source": "planalto",
        "source_file": "output_legislacao/x.md",
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9784.htm",
        "chunk_index": 0,
        "text": "Art. 1º Teste",
        "metadata": {"corpus": "legislacao_planalto_ingest"},
    }
    out = normalize_chunk_row(row)
    fp = doc_fingerprint(out["url"])
    assert out["id"] == f"{fp}-0"
    assert out["url"].startswith("https://")


def test_fix_text_encoding_mojibake():
    broken = "PresidÃªncia da RepÃºblica"
    fixed = fix_text_encoding(broken)
    assert "Presidência" in fixed or fixed != broken
