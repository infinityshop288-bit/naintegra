"""Testes de ingestão, preservação, pipeline e manifesto organizado."""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from naintegra_lex_agent.agent import collect_cycle
from naintegra_lex_agent.ingest import iter_records_from_file
from naintegra_lex_agent.pipeline import normalize_record, preservation_dict
from naintegra_lex_agent.preservation import copy_inbox_files_to_preservation
from naintegra_lex_agent.settings import Settings


class TestOrganizeJurisSumula(unittest.TestCase):
    """Organização (doc_type + organized + body) para jurisprudência e súmula."""

    def test_jurisprudencia_ementa_e_org(self) -> None:
        rec = {
            "id": "stj-esp-1",
            "type": "jurisprudencia",
            "titulo": "REsp representativo",
            "metadata": {
                "ementa": "EMENTA: Nega-se provimento ao recurso.",
                "tribunal": "STJ",
                "materia": "tributario",
            },
            "_source_byte_offset": 0,
        }
        doc = normalize_record(rec, Settings(ai_enabled=False), None, [999])
        assert doc is not None
        self.assertEqual(doc.doc_type.value, "jurisprudencia")
        self.assertEqual(doc.organized.get("tribunal"), "STJ")
        self.assertEqual(doc.organized.get("materia"), "Tributário")
        self.assertIn("EMENTA", doc.body or "")

    def test_sumula_enunciado_e_org(self) -> None:
        rec = {
            "id": "stf-sv-99",
            "type": "sumula",
            "titulo": "Súmula Vinculante 99",
            "texto": "Breve.",
            "enunciado": "Texto oficial do enunciado normativo da súmula.",
            "tribunal": "STF",
            "materia": "penal",
            "_source_byte_offset": 0,
        }
        doc = normalize_record(rec, Settings(ai_enabled=False), None, [999])
        assert doc is not None
        self.assertEqual(doc.doc_type.value, "sumula")
        self.assertEqual(doc.organized.get("tribunal"), "STF")
        self.assertEqual(doc.organized.get("materia"), "Penal")
        self.assertEqual(doc.body, "Texto oficial do enunciado normativo da súmula.")


class TestJsonlByteOffset(unittest.TestCase):
    def test_offset_points_to_line_start(self) -> None:
        base = Path("/tmp/naintegra_ut_jsonl")
        shutil.rmtree(base, ignore_errors=True)
        inbox = base / "inbox"
        inbox.mkdir(parents=True)
        # linha comentada + JSON (mesmo padrão do agente)
        p = inbox / "x.jsonl"
        p.write_bytes(b"# cab\n{\"id\":\"a\",\"type\":\"legislacao\",\"titulo\":\"T\",\"texto\":\"B\"}\n")

        rec = next(iter_records_from_file(p))
        off = rec["_source_byte_offset"]
        raw = p.read_bytes()
        self.assertTrue(raw[off:].startswith(b"{"))

    def test_preservation_dict_includes_offset(self) -> None:
        rec = {
            "_preservation_batch": "b1",
            "_preservation_file_relpath": "b1/f.jsonl",
            "_inbox_file_relpath": "f.jsonl",
            "_source_line": 2,
            "_source_byte_offset": 7,
            "_verbatim_payload_sha256": "abc",
            "id": "x",
            "titulo": "T",
            "texto": "B",
            "type": "legislacao",
        }
        d = preservation_dict(rec)
        self.assertEqual(d["preserved_line_byte_offset"], 7)


class TestNormalize(unittest.TestCase):
    def test_heuristic_legislacao(self) -> None:
        rec = {
            "id": "L1",
            "type": "legislacao",
            "titulo": "CF/88",
            "texto": "Art. 1º ...",
            "_preservation_batch": "b",
            "_inbox_file_relpath": "f.jsonl",
            "_source_line": 1,
            "_source_byte_offset": 0,
            "_verbatim_payload_sha256": "deadbeef",
        }
        s = Settings(ai_enabled=False)
        doc = normalize_record(rec, s, None, [999])
        assert doc is not None
        self.assertEqual(doc.doc_type.value, "legislacao")
        self.assertIn("preservation", doc.model_dump())
        self.assertEqual(doc.preservation.get("preserved_line_byte_offset"), 0)

    def test_sumula_from_text(self) -> None:
        rec = {
            "id": "S1",
            "titulo": "Súmula 1 — STF",
            "texto": "Enunciado.",
            "_source_byte_offset": 0,
        }
        s = Settings(ai_enabled=False)
        doc = normalize_record(rec, s, None, [999])
        assert doc is not None
        self.assertEqual(doc.doc_type.value, "sumula")


class TestCollectCycle(unittest.TestCase):
    def test_manifest_and_preservation(self) -> None:
        base = Path("/tmp/naintegra_ut_collect")
        shutil.rmtree(base, ignore_errors=True)
        inbox = base / "inbox"
        inbox.mkdir(parents=True)
        demo = inbox / "demo.jsonl"
        demo.write_bytes(
            b"# demo\n"
            + json.dumps(
                {
                    "id": "law-8112",
                    "type": "legislacao",
                    "titulo": "Lei 8.112/90",
                    "texto": "Art. 1º Regime jurídico dos servidores.",
                    "metadata": {"secao_lei_seca": "Constituição e Adm."},
                },
                ensure_ascii=False,
            ).encode("utf-8")
            + b"\n"
            + json.dumps(
                {
                    "id": "sv-10",
                    "type": "sumula",
                    "titulo": "Súmula Vinculante 10",
                    "texto": "Resumo: reserva de plenário (CF, art. 97).",
                    "enunciado": (
                        "Viola a cláusula de reserva de plenário (CF, art. 97) a decisão de órgão "
                        "fracionário de tribunal que, embora não declare expressamente a "
                        "inconstitucionalidade de lei ou ato normativo do poder público, afasta sua "
                        "incidência, no todo ou em parte."
                    ),
                    "tribunal": "STF",
                    "materia": "constitucional",
                    "metadata": {"vinculante": True},
                },
                ensure_ascii=False,
            ).encode("utf-8")
            + b"\n"
            + json.dumps(
                {
                    "id": "stj-tema-x",
                    "type": "jurisprudencia",
                    "titulo": "Tema repetitivo — ICMS",
                    "metadata": {
                        "ementa": "DIREITO TRIBUTÁRIO. Recurso especial improvido.",
                        "tribunal": "STJ",
                        "materia": "tributario",
                        "explicacao": (
                            "Estudo: precedentes do STJ tratam da não incidência em operações não "
                            "onerosas quando presentes os requisitos legais."
                        ),
                    },
                },
                ensure_ascii=False,
            ).encode("utf-8")
            + b"\n"
            + json.dumps(
                {
                    "id": "stf-s-enun",
                    "type": "sumula",
                    "titulo": "Súmula 500",
                    "texto": "Resumo para lista.",
                    "enunciado": "Enunciado completo da súmula para leitura integral.",
                    "tribunal": "STF",
                    "materia": "constitucional",
                },
                ensure_ascii=False,
            ).encode("utf-8")
            + b"\n",
        )

        settings = Settings(
            crawl_inbox_path=inbox,
            raw_preserved_path=base / "raw",
            organized_output_path=base / "org",
            preserve_inbox_files=True,
            write_organized_manifest=True,
            ai_enabled=False,
        )
        rows = collect_cycle(settings)
        self.assertEqual(len(rows), 4)

        by_id = {r["external_id"]: r for r in rows}
        self.assertEqual(by_id["stj-tema-x"]["doc_type"], "jurisprudencia")
        self.assertIn("TRIBUTÁRIO", by_id["stj-tema-x"]["body"].upper())
        self.assertEqual(by_id["stj-tema-x"]["organized"].get("tribunal"), "STJ")
        self.assertEqual(by_id["sv-10"]["organized"].get("materia"), "Constitucional")
        self.assertTrue(by_id["sv-10"]["organized"].get("vinculante"))
        self.assertIn("reserva de plenário", (by_id["sv-10"]["body"] or "").lower())
        exp_expected = (
            "Estudo: precedentes do STJ tratam da não incidência em operações não "
            "onerosas quando presentes os requisitos legais."
        )
        self.assertEqual(by_id["stj-tema-x"]["meta"].get("explicacao"), exp_expected)
        self.assertEqual(by_id["stf-s-enun"]["doc_type"], "sumula")
        self.assertEqual(by_id["stf-s-enun"]["body"], "Enunciado completo da súmula para leitura integral.")

        preserved = list((base / "raw").glob("**/demo.jsonl"))
        self.assertTrue(preserved)
        self.assertEqual(demo.read_bytes(), preserved[0].read_bytes())

        manifest = list((base / "org").glob("**/manifest.jsonl"))
        self.assertTrue(manifest)
        lines = manifest[0].read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(lines), 4)
        for ln in lines:
            row = json.loads(ln)
            self.assertIn("preservation", row)
            self.assertIn("verbatim", row)
            self.assertIn("organization", row)
            self.assertIn("preserved_line_byte_offset", row["preservation"])
            if row["external_id"] == "stj-tema-x":
                self.assertEqual(row["verbatim"].get("explicacao"), exp_expected)
                self.assertNotIn("explicacao", row["verbatim"].get("meta") or {})

    def test_analyzed_output_manifest_parallel_sink(self) -> None:
        base = Path("/tmp/naintegra_ut_analyzed")
        shutil.rmtree(base, ignore_errors=True)
        inbox = base / "inbox"
        inbox.mkdir(parents=True)
        demo = inbox / "one.jsonl"
        demo.write_text(
            json.dumps(
                {
                    "id": "only-one",
                    "type": "legislacao",
                    "titulo": "Lei X",
                    "texto": "Art único.",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        settings = Settings(
            crawl_inbox_path=inbox,
            raw_preserved_path=base / "raw",
            organized_output_path=base / "org",
            analyzed_output_enabled=True,
            analyzed_output_path=base / "analyzed",
            preserve_inbox_files=False,
            write_organized_manifest=True,
            ai_enabled=False,
            organized_batch_id="batch-test",
        )
        rows = collect_cycle(settings)
        self.assertEqual(len(rows), 1)
        am = base / "analyzed" / "batch-test" / "manifest.jsonl"
        self.assertTrue(am.is_file())
        om = base / "org" / "batch-test" / "manifest.jsonl"
        self.assertTrue(om.is_file())
        self.assertEqual(am.read_text(encoding="utf-8"), om.read_text(encoding="utf-8"))


class TestCopyPreservation(unittest.TestCase):
    def test_mapping_relative_path(self) -> None:
        base = Path("/tmp/naintegra_ut_copy")
        shutil.rmtree(base, ignore_errors=True)
        raw_root = base / "raw"
        raw_root.mkdir(parents=True)
        inbox = base / "inbox"
        inbox.mkdir(parents=True)
        f = inbox / "a.jsonl"
        f.write_text("{}\n", encoding="utf-8")
        m = copy_inbox_files_to_preservation([f], raw_root, "batch1")
        rel = m[f.resolve()]
        self.assertTrue(rel.startswith("batch1/"))
        dest = raw_root / rel
        self.assertEqual(dest.read_text(), "{}\n")


if __name__ == "__main__":
    unittest.main()
