"""Defaults do organize/questions loop."""

from __future__ import annotations

from naintegra_lex_agent.organize_loop import apply_loop_defaults
from naintegra_lex_agent.settings import Settings


def test_apply_loop_defaults_enables_analyzed_without_supabase() -> None:
    s = Settings(
        supabase_url=None,
        supabase_service_role_key=None,
        analyzed_output_enabled=False,
    )
    out = apply_loop_defaults(s)
    assert out.analyzed_output_enabled is True
    assert out.material_merge_before_cycle is True


def test_apply_loop_defaults_keeps_analyzed_flag_when_supabase_configured() -> None:
    s = Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="secret",
        analyzed_output_enabled=False,
    )
    out = apply_loop_defaults(s)
    assert out.analyzed_output_enabled is False
