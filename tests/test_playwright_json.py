"""Sanidade do parser JSON usado no harvest Playwright."""

from naintegra_lex_agent.concurso_study import playwright_capture as pc


def test_maybe_parse_json_accepts_utf8_bom() -> None:
    raw = "\ufeff{\"questao\": 1}".encode("utf-8")
    assert pc._maybe_parse_json(raw) == {"questao": 1}


def test_maybe_parse_json_trims_before_parse() -> None:
    assert pc._maybe_parse_json(b'  \n{"a": true}') == {"a": True}


def test_maybe_parse_json_rejects_html() -> None:
    assert pc._maybe_parse_json(b"<!DOCTYPE html><html>") is None
