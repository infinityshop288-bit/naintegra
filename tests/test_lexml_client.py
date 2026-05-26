"""Testes do cliente LEXML (parse HTML / crawl JSONL)."""

import unittest

from naintegra_lex_agent.lexml_client import (
    hit_from_crawl_record,
    merge_hits,
    parse_br_date,
    parse_search_html,
    LexmlHit,
)

SAMPLE_HIT = """
<div id="main_1" class="docHit"><table>
<tr><td class="col1"><b>1</b></td><td class="col2"><b>Autoridade</b></td><td class="col3">Federal</td></tr>
<tr><td class="col1"></td><td class="col2"><b>Título</b></td><td class="col3"><a href="/urn/urn:lex:br:federal:lei:2022-06-14;14368">Lei nº 14.368, de 14 de Junho de 2022</a></td></tr>
<tr><td class="col1"></td><td class="col2"><b>Data</b></td><td class="col3">14/06/2022</td></tr>
<tr><td class="col1"></td><td class="col2"><b>Ementa</b></td><td class="col3">Altera a Lei nº 8.666/1993.</td></tr>
<tr><td class="col1"></td><td class="col2"><b>URN</b></td><td class="col3">urn:lex:br:federal:lei:2022-06-14;14368</td></tr>
</table></div>
"""


class TestLexmlClient(unittest.TestCase):
    def test_parse_search_html(self) -> None:
        hits = parse_search_html(SAMPLE_HIT)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].urn, "urn:lex:br:federal:lei:2022-06-14;14368")
        self.assertIn("8.666", hits[0].ementa)
        self.assertEqual(hits[0].date, parse_br_date("14/06/2022"))

    def test_hit_from_crawl_record(self) -> None:
        rec = {
            "urn": "urn:lex:br:federal:lei:2015-03-16;13105",
            "titulo": "Lei 13105",
            "ementa": "Altera dispositivos.",
            "source": "lexml",
            "doc_type": "legislacao",
        }
        hit = hit_from_crawl_record(rec)
        assert hit is not None
        self.assertEqual(hit.urn, rec["urn"])
        self.assertEqual(hit.source, "crawl_inbox")

    def test_merge_hits_dedupes(self) -> None:
        a = LexmlHit(urn="urn:lex:br:federal:lei:2022-06-14;14368", title="A")
        b = LexmlHit(
            urn="urn:lex:br:federal:lei:2022-06-14;14368",
            title="A",
            ementa="Altera 8666",
        )
        merged = merge_hits([a], [b])
        self.assertEqual(len(merged), 1)
        self.assertIn("8666", merged[0].ementa)


if __name__ == "__main__":
    unittest.main()
