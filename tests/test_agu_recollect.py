from __future__ import annotations

from naintegra_lex_agent.agu_recollect import (
    has_encoding_corruption,
    needs_planalto_recollection,
    build_recollection_record,
)


def test_has_encoding_corruption_fffd():
    assert has_encoding_corruption("Presid\ufffdncia")


def test_has_encoding_corruption_ok():
    assert not has_encoding_corruption("Presidência da República")


def test_needs_recollection_planalto():
    rec = {
        "url": "https://www.planalto.gov.br/ccivil_03/decreto/d1171.htm",
        "content": "Presid\ufffdncia da Rep\ufffdblica",
    }
    assert needs_planalto_recollection(rec)


def test_build_recollection_record():
    src = {
        "title": "Decreto 1171",
        "url": "https://www.planalto.gov.br/ccivil_03/decreto/d1171.htm",
        "tags": ["agu:dec_1171"],
    }
    row = build_recollection_record(
        src,
        content="Presidência da República\nDECRETO Nº 1.171",
        recollection_source="test",
    )
    assert row["collection"] == "legislacao_agu_recollection"
    assert row["encoding_verified"] is True
    assert "Presidência" in row["content"]
