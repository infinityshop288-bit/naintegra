"""Supabase sink — comportamento sem credenciais."""

from __future__ import annotations

from naintegra_lex_agent.settings import Settings
from naintegra_lex_agent.supabase_sink import upsert_batches


def test_upsert_batches_no_credentials_returns_false() -> None:
    settings = Settings(supabase_url=None, supabase_service_role_key=None, dry_run=False)
    assert upsert_batches([{"external_id": "a"}], settings) is False


def test_upsert_batches_empty_rows_returns_false() -> None:
    settings = Settings(supabase_url="http://x", supabase_service_role_key="k")
    assert upsert_batches([], settings) is False


def test_upsert_batches_dry_run_returns_true() -> None:
    settings = Settings(dry_run=True)
    assert upsert_batches([{"external_id": "a"}], settings) is True
