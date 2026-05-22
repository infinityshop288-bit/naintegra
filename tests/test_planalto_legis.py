from __future__ import annotations

from naintegra_lex_agent.planalto_legis import (
    PLANALTO_LEGIS_CATALOG,
    content_hash,
    html_to_lex_text,
    merge_catalog,
    normalize_for_hash,
)


SAMPLE_HTML = """
<html><body>
<p>Art. 1º Texto vigente da norma.</p>
<p>Art. 2º <s>Redação revogada antiga.</s> Texto atualizado do artigo.</p>
<p>§ 1º Dispositivo. <span style="text-decoration: line-through">trecho revogado</span> continuação.</p>
<p>(Redação dada pela Lei nº 14.155, de 2021)</p>
</body></html>
"""


def test_html_to_lex_preserves_revoked_markers():
    text = html_to_lex_text(SAMPLE_HTML)
    assert "~~Redação revogada antiga.~~" in text
    assert "~~trecho revogado~~" in text
    assert "Redação dada pela Lei nº 14.155" in text
    assert "Texto vigente" in text


def test_content_hash_stable():
    a = content_hash("Art. 1º  Teste")
    b = content_hash("Art. 1º Teste")
    assert a == b


def test_normalize_for_hash_collapses_whitespace():
    assert normalize_for_hash("a\n\n  b") == "a b"


def test_catalog_includes_penal_core_laws():
    urls = {item["url"] for item in PLANALTO_LEGIS_CATALOG}
    assert any("del2848" in u for u in urls)
    assert any("l11340" in u for u in urls)
    assert any("l7210" in u for u in urls)


def test_merge_catalog_dedupes():
    extra = {"url": PLANALTO_LEGIS_CATALOG[1]["url"], "titulo": "dup", "secao": "x"}
    merged = merge_catalog(extra)
    assert len(merged) == len(PLANALTO_LEGIS_CATALOG)
