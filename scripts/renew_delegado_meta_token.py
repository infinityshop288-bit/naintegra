#!/usr/bin/env python3
"""Renova META_ACCESS_TOKEN (Page Token) — só META_ACCESS_TOKEN no .env.

Uso recomendado (evita erro de domínio localhost):
  python3 scripts/renew_delegado_meta_token.py

Alternativas:
  python3 scripts/renew_delegado_meta_token.py --page-token TOKEN   # Graph Explorer
  python3 scripts/renew_delegado_meta_token.py --user-token TOKEN   # one-shot
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from naintegra_meta.env_file import patch_env
from naintegra_meta.oauth_local import build_oauth_url, renew_via_manual_oauth
from naintegra_meta.settings import MetaSettings
from naintegra_meta.token_sync import MetaTokenSyncError, debug_token, page_token_from_user_token, save_page_token_direct, verify_pairing


def main() -> int:
    parser = argparse.ArgumentParser(description="Renova META_ACCESS_TOKEN")
    parser.add_argument("--user-token", default="", help="User token, uso único na CLI")
    parser.add_argument("--page-token", default="", help="Page token direto do Graph Explorer")
    parser.add_argument("--convert", action="store_true", help="Converte USER token atual em Page Token")
    parser.add_argument("--print-oauth-url", action="store_true", help="Só imprime URL OAuth Meta")
    args = parser.parse_args()

    settings = MetaSettings()
    app_id = settings.meta_app_id or ""
    app_secret = settings.meta_app_secret or ""
    if not app_id or not app_secret:
        print("META_APP_ID e META_APP_SECRET obrigatórios no .env", file=sys.stderr)
        return 1

    if args.print_oauth_url:
        print(build_oauth_url(app_id))
        return 0

    try:
        if args.page_token:
            updates = save_page_token_direct(args.page_token.strip(), settings)
        elif args.user_token:
            updates = page_token_from_user_token(app_id, app_secret, args.user_token.strip())
        elif args.convert:
            token = settings.meta_access_token or ""
            if not token:
                raise MetaTokenSyncError("META_ACCESS_TOKEN vazio no .env")
            dbg = debug_token(token, app_id, app_secret)
            if not dbg.get("is_valid"):
                err = (dbg.get("error") or {}).get("message", "token inválido")
                raise MetaTokenSyncError(err)
            if dbg.get("type") == "PAGE":
                check = verify_pairing(settings)
                print("✓ Já é Page Token válido")
                print(f"  Seguidores: {check['checks'].get('followers', '?')}")
                return 0
            print("Convertendo USER → Page Token…")
            updates = page_token_from_user_token(app_id, app_secret, token)
        else:
            check = verify_pairing(settings)
            checks = check.get("checks") or {}
            if check.get("valid") and checks.get("token_type") == "PAGE":
                print("✓ META_ACCESS_TOKEN já válido e pareado com @delegadoluizcarlos")
                print(f"  Seguidores: {checks.get('followers', '?')}")
                return 0
            if checks.get("token_valid") and checks.get("token_type") == "USER":
                print("Token USER válido — convertendo para Page Token…")
                updates = page_token_from_user_token(app_id, app_secret, settings.meta_access_token or "")
            elif check.get("valid"):
                print("✓ META_ACCESS_TOKEN já válido e pareado com @delegadoluizcarlos")
                print(f"  Seguidores: {checks.get('followers', '?')}")
                return 0
            else:
                print("Token inválido — abrindo OAuth Meta (redirect oficial, sem localhost)…")
                updates = renew_via_manual_oauth(app_id, app_secret)
    except MetaTokenSyncError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    patch_env(updates)
    print("✓ META_ACCESS_TOKEN (Page Token) salvo no .env")
    print(f"  FB_PAGE_ID={updates['FB_PAGE_ID']}")
    print(f"  IG_USER_ID={updates['IG_USER_ID']}")
    print("\nRode: python3 scripts/test_delegado_pairing.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
