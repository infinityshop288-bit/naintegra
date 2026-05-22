"""Testes do extrator de dispositivo legal."""

import unittest

from naintegra_lex_agent.legal_text import pick_explicacao, pick_verbatim_body


class TestLegalText(unittest.TestCase):
    def test_dispositivo_priority_over_texto(self) -> None:
        r = {
            "texto": "Ementa curta.",
            "dispositivo": "Art. 1º Norma jurídica completa aqui.",
        }
        self.assertEqual(pick_verbatim_body(r), "Art. 1º Norma jurídica completa aqui.")

    def test_nested_metadata_dispositivo(self) -> None:
        r = {"metadata": {"dispositivo": "Art. 2º Somente no meta."}}
        self.assertEqual(pick_verbatim_body(r), "Art. 2º Somente no meta.")

    def test_artigos_list(self) -> None:
        r = {
            "artigos": [
                {"numero": "1", "texto": "Primeiro parágrafo."},
                {"numero": "2", "texto": "Segundo."},
            ]
        }
        b = pick_verbatim_body(r)
        assert b is not None
        self.assertIn("Art. 1", b)
        self.assertIn("Primeiro", b)

    def test_sumula_enunciado_over_texto(self) -> None:
        r = {
            "texto": "Resumo para card.",
            "enunciado": "É ilegal o tratamento discriminatório previsto na súmula oficial.",
        }
        self.assertEqual(
            pick_verbatim_body(r),
            "É ilegal o tratamento discriminatório previsto na súmula oficial.",
        )

    def test_pick_explicacao_top_level_e_metadata(self) -> None:
        flat = {"ementa": "Ementa só.", "explicacao": " Comentário didático. "}
        self.assertEqual(pick_explicacao(flat), "Comentário didático.")
        nested = {"metadata": {"explicacao": "No meta."}}
        self.assertEqual(pick_explicacao(nested), "No meta.")

    def test_juris_ementa_metadata(self) -> None:
        r = {
            "titulo": "REsp 1.234",
            "metadata": {
                "ementa": "DIREITO TRIBUTÁRIO. ICMS. Recurso provido.",
                "tribunal": "STJ",
            },
        }
        self.assertEqual(
            pick_verbatim_body(r),
            "DIREITO TRIBUTÁRIO. ICMS. Recurso provido.",
        )


if __name__ == "__main__":
    unittest.main()
