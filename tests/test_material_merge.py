"""Fusão de corpus JSONL."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from naintegra_lex_agent.material_merge import merge_material_into_corpus
from naintegra_lex_agent.settings import Settings


class TestMaterialMerge(unittest.TestCase):
    def test_merge_dedup_and_extra_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            extra = Path(td) / "extra"
            inbox.mkdir()
            extra.mkdir()

            a = inbox / "corpus.jsonl"
            a.write_text(
                json.dumps({"id": "x", "titulo": "Primeiro", "texto": "A"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            extra_f = extra / "more.jsonl"
            extra_f.write_text(
                json.dumps({"id": "x", "titulo": "Sobrescrito", "texto": "B"}, ensure_ascii=False)
                + "\n"
                + json.dumps({"id": "y", "titulo": "Outro", "texto": "C"}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )

            s = Settings(
                crawl_inbox_path=inbox,
                material_merge_before_cycle=False,
                material_merge_extra_roots=str(extra),
                corpus_output_name="corpus.jsonl",
            )
            merge_material_into_corpus(s)
            out = a.read_text(encoding="utf-8").strip().split("\n")
            self.assertTrue(out[0].startswith("#"))
            body = [json.loads(line) for line in out[1:]]
            by_id = {r["id"]: r for r in body}
            self.assertEqual(by_id["x"]["titulo"], "Sobrescrito")
            self.assertIn("y", by_id)


if __name__ == "__main__":
    unittest.main()
