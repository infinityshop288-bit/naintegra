#!/usr/bin/env python3
"""Diagnostica permissões Meta faltantes e abre links de configuração."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from naintegra_meta.env_file import patch_env
from naintegra_meta.meta_permissions import (
    missing_scopes,
    permissions_report,
    renew_with_insights_scope,
)
from naintegra_meta.meta_permissions import MetaPermissionsError
from naintegra_meta.settings import MetaSettings
from naintegra_meta.token_sync import MetaTokenSyncError, page_token_from_user_token


def main() -> int:
    parser = argparse.ArgumentParser(description="Corrige permissões Meta do dashboard")
    parser.add_argument("--user-token", default="", help="User token reautorizado (converte para Page)")
    parser.add_argument("--open-links", action="store_true", help="Abre OAuth e Business Manager")
    parser.add_argument("--apply", action="store_true", help="Salva Page Token após --user-token")
    args = parser.parse_args()

    settings = MetaSettings()
    report = permissions_report(settings)
    links = report.get("setup_links") or {}

    print("\n=== Permissões Meta @delegadoluizcarlos ===\n")
    print(f"  Token: {'válido' if report.get('token_valid') else 'inválido'} ({report.get('token_type')})")
    print(f"  Business ID: {report.get('business_id') or '—'}")
    missing = report.get("missing_required") or {}
    if missing:
        print("\n  Permissões faltando:")
        for scope, label in missing.items():
            print(f"    ✗ {scope} — {label}")
    else:
        print("\n  ✓ Permissões obrigatórias presentes")

    if args.user_token:
        try:
            if missing:
                updates = renew_with_insights_scope(settings, args.user_token)
            else:
                updates = page_token_from_user_token(
                    settings.meta_app_id or "",
                    settings.meta_app_secret or "",
                    args.user_token.strip(),
                )
        except (MetaPermissionsError, MetaTokenSyncError) as exc:
            print(f"\nErro: {exc}", file=sys.stderr)
            return 1
        patch_env(updates)
        print("\n✓ Page Token salvo no .env")
        return 0

    print("\n  Links úteis:")
    for key, url in links.items():
        print(f"    {key}: {url}")

    print("\n  Passos:")
    print("  1) Graph Explorer → Generate Token → marque instagram_manage_insights + ads_read")
    print("  2) Get Page Access Token → Infinity - Digital")
    print("  3) Business Manager → Conta de anúncios → Adicionar app Claude (2257277374806887)")
    print("  4) python3 scripts/renew_delegado_meta_token.py --page-token \"EAA...\"")

    if args.open_links:
        for url in [links.get("graph_explorer"), links.get("assign_ad_account"), links.get("oauth")]:
            if url:
                webbrowser.open(url)

    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
