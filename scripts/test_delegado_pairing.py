#!/usr/bin/env python3
"""Testa pareamento Page Facebook ↔ Instagram ↔ META_ACCESS_TOKEN ↔ dashboard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import httpx

from naintegra_meta.settings import MetaSettings
from naintegra_meta.token_sync import verify_pairing

EXPECTED_EMAIL = "infinity.shop288@gmail.com"


def main() -> int:
    env = MetaSettings()
    print("\n=== Teste de pareamento @delegadoluizcarlos ===\n")

    pairing = verify_pairing(env)
    checks = pairing.get("checks") or {}

    if checks.get("token_valid"):
        print(f"  ✓ meta_token: type={checks.get('token_type')} scopes={checks.get('scopes')}")
    else:
        err = checks.get("token_error") or checks.get("token") or "inválido"
        print(f"  ✗ meta_token: {err}")

    if pairing.get("valid"):
        print(f"  ✓ page_ig_pairing: «{checks.get('page_name')}» → @{checks.get('ig_username')}")
        print(f"  ✓ ig_id_match: seguidores={checks.get('followers')}")
    elif checks.get("token_valid"):
        print(f"  ✗ page_ig_pairing: {checks.get('page_error') or 'IDs não batem'}")
    else:
        print("  ✗ page_ig_pairing: token inválido — rode: python3 scripts/renew_delegado_meta_token.py")

    sb_ok = False
    sb_url = (env.supabase_url or "").rstrip("/")
    sb_key = env.supabase_anon_key or ""
    if sb_url and sb_key:
        r = httpx.get(
            f"{sb_url}/rest/v1/content_queue",
            headers={"apikey": sb_key, "Accept-Profile": "delegado"},
            params={"select": "id", "limit": "1"},
            timeout=15,
        )
        ok = r.status_code == 200
        sb_ok = ok
        print(f"  {'✓' if ok else '✗'} supabase_delegado: REST HTTP {r.status_code}")

    cfg = ROOT / "web/delegado/js/config.js"
    if cfg.exists():
        txt = cfg.read_text(encoding="utf-8")
        print(f"  {'✓' if env.supabase_url in txt else '✗'} frontend_supabase")
        print(f"  {'✓' if EXPECTED_EMAIL in txt else '✗'} frontend_email")

    paired = pairing.get("valid", False) and sb_ok
    print(f"\n{'PAREAMENTO OK' if paired else 'PAREAMENTO FALHOU'}\n")

    out = ROOT / "data" / "delegado_pairing.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"paired": paired, "pairing": pairing}, ensure_ascii=False, indent=2))

    return 0 if paired else 1


if __name__ == "__main__":
    raise SystemExit(main())
