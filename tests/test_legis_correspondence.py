from __future__ import annotations

from naintegra_lex_agent.legis_correspondence import (
    ementa_matches_body,
    identity_from_body,
    identity_from_title,
    identity_from_url,
    verify_record,
)


def test_identity_from_title_decreto():
    ident = identity_from_title("Decreto 1171")
    assert ident is not None
    assert ident.act_type == "decreto"
    assert ident.number_digits == "1171"


def test_identity_from_title_lei_complementar():
    ident = identity_from_title("Lei Complementar 73")
    assert ident is not None
    assert ident.act_type == "lei_complementar"
    assert ident.number_digits == "73"


def test_identity_from_title_mpv():
    ident = identity_from_title("Medida Provisória 2170-36")
    assert ident is not None
    assert ident.act_type == "medida_provisoria"
    assert ident.number_digits == "2170"
    assert ident.number_suffix == "36"


def test_identity_from_url_planalto():
    ident = identity_from_url("https://www.planalto.gov.br/ccivil_03/decreto/d1171.htm")
    assert ident is not None
    assert ident.number_digits == "1171"


def test_identity_from_url_lexml():
    ident = identity_from_url(
        "https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:2011-08-04;12462"
    )
    assert ident is not None
    assert ident.act_type == "lei"
    assert ident.number_digits == "12462"


def test_identity_from_body_matches_formatted_number():
    text = "DECRETO Nº 3.048, DE 6 DE MAIO DE 1999.\nAprova o Regulamento."
    ident = identity_from_body(text)
    assert ident is not None
    assert ident.number_digits == "3048"


def test_verify_record_ok_lexml():
    record = {
        "title": "Lei 12462",
        "url": "https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:2011-08-04;12462",
        "legal_act_type": "lei",
        "tags": ["agu:lei_12462"],
        "content": (
            "Título Lei nº 12.462, de 4 de Agosto de 2011\n\n"
            "Ementa Institui o Regime Diferenciado de Contratações Públicas.\n\n"
            "Art. 1º Texto da lei."
        ),
        "summary": "Ementa Institui o Regime Diferenciado de Contratações Públicas.",
    }
    report = verify_record(record)
    assert report.ok
    assert not report.skipped


def test_verify_record_mismatch():
    record = {
        "title": "Decreto 1171",
        "url": "https://www.planalto.gov.br/ccivil_03/decreto/d2799.htm",
        "legal_act_type": "decreto",
        "content": "DECRETO Nº 2.799, DE 8 DE OUTUBRO DE 1998.",
    }
    report = verify_record(record)
    assert not report.ok
    codes = {i.code for i in report.issues}
    assert "NUMBER_TITLE_URL" in codes


def test_ementa_matches_body():
    ementa = "Institui o Regime Diferenciado de Contratações Públicas"
    body = "Ementa " + ementa + "\n\nArt. 1º Dispositivo."
    assert ementa_matches_body(ementa, body)
