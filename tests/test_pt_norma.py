from __future__ import annotations

from naintegra_lex_agent.pt_norma import (
    VERSION,
    apply_pt_norma,
    domain_for_doc_type,
    normalize_lei_references,
)
from naintegra_lex_agent.norma_chunks import normalize_chunk_row, reapply_pt_norma_rows
from naintegra_lex_agent.pt_norma import VERSION as PT_NORMA_VERSION


def test_version_matches_lex_frontend():
    assert VERSION == 2


def test_apply_fixes_accents_and_citations():
    raw = (
        "O agente publico nao podera praticar ato. "
        "Nos termos do art. 5o da Constituicao Federal , o habeas corpus sera concedido."
    )
    out = apply_pt_norma(raw, domain="legis")
    assert "público" in out
    assert "não poderá" in out
    assert "Constituição Federal" in out
    assert "art. 5º" in out
    assert "será" in out


def test_sumula_vinculante_not_split():
    out = apply_pt_norma("Sumula Vinculante 10 - Reserva de plenario", domain="juris")
    assert "Súmula Vinculante" in out
    assert "Vincul ante" not in out
    assert "plenário" in out


def test_normalize_lei_references():
    t = normalize_lei_references("Lei nº 8.112, de 11 de dezembro de 1990")
    assert "Lei 8.112/1990" in t


def test_domain_for_doc_type():
    assert domain_for_doc_type("legislacao") == "legis"
    assert domain_for_doc_type("sumula") == "juris"
    assert domain_for_doc_type(None, "planalto") == "legis"


def test_reapply_pt_norma_rows_only_stale():
    rows = [
        {
            "id": "a-0",
            "source": "planalto",
            "source_file": "x.md",
            "url": "https://www.planalto.gov.br/ccivil_03/leis/l8112.htm",
            "chunk_index": 0,
            "text": "Art. 1º O servidor publico nao podera.",
            "metadata": {},
        },
        {
            "id": "b-0",
            "source": "planalto",
            "source_file": "y.md",
            "url": "https://www.planalto.gov.br/ccivil_03/leis/l8666.htm",
            "chunk_index": 0,
            "text": "Art. 1º Texto já normalizado.",
            "metadata": {"pt_norma_version": PT_NORMA_VERSION},
        },
    ]
    out, changed, skipped = reapply_pt_norma_rows(rows, only_stale=True)
    assert changed == 1
    assert skipped == 1
    assert len(out) == 1
    assert "público" in out[0]["text"]


def test_normalize_chunk_row_applies_pt_norma():
    row = {
        "id": "x-0",
        "source": "planalto",
        "source_file": "output_legislacao/x.md",
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l8112.htm",
        "chunk_index": 0,
        "text": "Art. 1º O servidor publico nao podera receber vantagem.",
        "metadata": {},
    }
    out = normalize_chunk_row(row)
    assert "público" in out["text"]
    assert "não poderá" in out["text"]
    assert out["metadata"].get("pt_norma_version") == PT_NORMA_VERSION
