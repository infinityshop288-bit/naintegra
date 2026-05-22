"""Extração de questões de prova e gabaritos."""

from __future__ import annotations

import unittest

from naintegra_lex_agent.exam_questions import (
    format_alternativas,
    pick_gabarito_objetivo,
    pick_questoes_body,
    prime_meta_for_doc_inference,
)
from naintegra_lex_agent.pipeline import normalize_record
from naintegra_lex_agent.settings import Settings
from naintegra_lex_agent.taxonomy import infer_doc_type


class TestExamQuestions(unittest.TestCase):
    def test_format_alternativas_list(self) -> None:
        alt = format_alternativas(
            [{"letra": "A", "texto": "Sim"}, {"letra": "B", "texto": "Não"}],
        )
        assert alt is not None
        self.assertIn("A) Sim", alt)
        self.assertIn("B) Não", alt)

    def test_pick_questoes_body_composto(self) -> None:
        rec = {
            "type": "questoes_objetivas",
            "titulo": "Prova demo — Q 1",
            "metadata": {
                "texto_questao": "Marque a incorreta.",
                "alternativas": [{"letra": "A", "texto": "Um"}],
                "gabarito": "A",
            },
        }
        body = pick_questoes_body(rec)
        assert body is not None
        self.assertIn("Marque a incorreta.", body)
        self.assertIn("A) Um", body)
        self.assertIn("Gabarito (objetiva): A", body)

    def test_prime_meta_eleva_gabarito_aninhado(self) -> None:
        meta = {}
        clean = {"meta": {"gabarito": "C", "alternativas": []}}
        out = prime_meta_for_doc_inference(meta, clean)
        self.assertEqual(out.get("gabarito"), "C")

    def test_infer_objetiva_por_alternativas_e_gabarito(self) -> None:
        meta = {"alternativas": [{"letra": "A"}], "gabarito": "A"}
        self.assertEqual(infer_doc_type(None, meta), "questoes_objetivas")

    def test_normalize_questao_objetiva_pipeline(self) -> None:
        rec = {
            "id": "cespe-q-01",
            "type": "questoes_objetivas",
            "titulo": "CESPE 2024 — Questão 1",
            "metadata": {
                "texto_questao": "É correto afirmar que ...",
                "alternativas": [
                    {"letra": "A", "texto": "Certo."},
                    {"letra": "B", "texto": "Errado."},
                ],
                "resposta_correta": "B",
                "banca": "cespe",
                "ano": 2024,
                "materia": "administrativo",
                "numero_questao": 1,
            },
            "_source_byte_offset": 0,
        }
        doc = normalize_record(rec, Settings(ai_enabled=False), None, [999])
        assert doc is not None
        self.assertEqual(doc.doc_type.value, "questoes_objetivas")
        self.assertEqual(doc.organized.get("banca"), "CESPE")
        self.assertEqual(doc.organized.get("ano"), 2024)
        self.assertEqual(doc.meta.get("gabarito"), "B")
        self.assertIn("Gabarito (objetiva): B", doc.body or "")

    def test_normalize_questao_subjetiva_pipeline(self) -> None:
        rec = {
            "id": "fgv-q-disc",
            "doc_type": "questoes_subjetivas",
            "titulo": "FGV — Discursiva 2",
            "meta": {
                "enunciado_questao": "Discorra sobre improbidade.",
                "resposta_modelo": "Deve abordar LP ...",
                "banca": "fgv",
                "materia": "constitucional",
            },
            "_source_byte_offset": 0,
        }
        doc = normalize_record(rec, Settings(ai_enabled=False), None, [999])
        assert doc is not None
        self.assertEqual(doc.doc_type.value, "questoes_subjetivas")
        self.assertEqual(pick_gabarito_objetivo(rec), None)
        self.assertIn("Discorra sobre improbidade.", doc.body or "")
        self.assertIn("Resposta de referência", doc.body or "")
