#!/usr/bin/env python3
"""Abre Graph API Explorer e imprime passos para obter META_ACCESS_TOKEN."""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from naintegra_meta.settings import MetaSettings
from naintegra_meta.oauth_local import build_oauth_url

APP_ID = "2257277374806887"
EXPLORER = f"https://developers.facebook.com/tools/explorer/{APP_ID}/"

STEPS = """
╔══════════════════════════════════════════════════════════════╗
║  META_ACCESS_TOKEN — @delegadoluizcarlos                     ║
╠══════════════════════════════════════════════════════════════╣
║  Graph API Explorer (recomendado):                           ║
║  1. Generate Access Token → autorize permissões IG/Pages     ║
║  2. Get Page Access Token → Infinity - Digital               ║
║  3. Copie o token (EAA…)                                     ║
║  4. Rode:                                                    ║
║     python3 scripts/renew_delegado_meta_token.py \\          ║
║       --page-token "EAA..."                                  ║
╠══════════════════════════════════════════════════════════════╣
║  OAuth alternativo:                                          ║
║     python3 scripts/renew_delegado_meta_token.py             ║
║  (cole access_token da URL após login)                       ║
╚══════════════════════════════════════════════════════════════╝
"""


def main() -> int:
    print(STEPS)
    print(f"Explorer: {EXPLORER}\n")
    settings = MetaSettings()
    if settings.meta_app_id:
        print(f"OAuth: {build_oauth_url(settings.meta_app_id)}\n")
    webbrowser.open(EXPLORER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
