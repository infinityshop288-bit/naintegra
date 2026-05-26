"""Testes de interpretação de impacto jurídico (LEXML/crawl)."""

import unittest

from naintegra_lex_agent.lexml_impact import (
    ImpactKind,
    analyze_impact,
    catalog_urls_for_law_numbers,
    crawl_record_from_hit,
    extract_law_numbers,
    normalize_law_number,
    should_remove_entire_law,
)


class TestLexmlImpact(unittest.TestCase):
    def test_extract_law_numbers(self) -> None:
        nums = extract_law_numbers("Altera a Lei nº 8.666/1993 e a Lei 10.406/2002")
        self.assertIn("8666/1993", nums)
        self.assertIn("10406/2002", nums)

    def test_analyze_revoke(self) -> None:
        report = analyze_impact(
            title="Lei nº 14.000/2020",
            ementa="Revoga a Lei nº 8.666, de 21 de junho de 1993.",
        )
        self.assertTrue(report.has_revocation())
        self.assertEqual(report.actions[0].kind, ImpactKind.REVOKE)
        self.assertIn("8666", report.actions[0].target_law_numbers)

    def test_catalog_urls_for_law_numbers(self) -> None:
        catalog = [
            {"url": "http://www.planalto.gov.br/ccivil_03/leis/l8666cons.htm", "titulo": "Lei 8666"},
            {"url": "http://www.planalto.gov.br/ccivil_03/leis/l8078.htm", "titulo": "CDC"},
        ]
        found = catalog_urls_for_law_numbers(catalog, {"8666"})
        self.assertEqual(len(found), 1)
        self.assertIn("8666", found[0]["url"])

    def test_should_remove_entire_law(self) -> None:
        body = "~~Art. 1º Revogado.~~\n~~Art. 2º Revogado.~~\n~~Art. 3º Revogado.~~"
        self.assertTrue(should_remove_entire_law(title="Lei revogada", body=body))

    def test_crawl_record_from_hit(self) -> None:
        hit = {"urn": "urn:lex:br:federal:lei:2022-06-14;14368", "title": "Lei 14368"}
        report = analyze_impact(
            title="Lei 14368",
            ementa="Altera a Lei nº 8.666/1993.",
            urn=hit["urn"],
        )
        rec = crawl_record_from_hit(hit, report)
        self.assertEqual(rec["source"], "lexml")
        self.assertEqual(rec["doc_type"], "legislacao")
        self.assertIn("8666/1993", rec["metadata"]["leis_alvo"])

    def test_normalize_law_number(self) -> None:
        self.assertEqual(normalize_law_number("8.666/1993"), "8666/1993")


if __name__ == "__main__":
    unittest.main()
