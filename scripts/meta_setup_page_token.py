#!/usr/bin/env python3
"""Obtém Page Access Token Meta com permissões Instagram e atualiza .env.

Uso interativo:
  python3 scripts/meta_setup_page_token.py

Uso não-interativo (após login no Graph API Explorer):
  python3 scripts/meta_setup_page_token.py \\
    --app-id SEU_APP_ID \\
    --app-secret SEU_APP_SECRET \\
    --short-token TOKEN_CURTA_DURACAO
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import httpx

API_VERSION = "v23.0"
GRAPH = f"https://graph.facebook.com/{API_VERSION}"
ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
DEFAULT_APP_ID = "1297761315887700"

SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "instagram_basic",
    "instagram_content_publish",
    "instagram_manage_comments",
    "ads_read",
    "business_management",
]


def load_env() -> dict[str, str]:
    data: dict[str, str] = {}
    if not ENV_PATH.exists():
        return data
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        data[k.strip()] = v.strip()
    return data


def save_env(updates: dict[str, str]) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    keys = set(updates)
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=", 1)[0].strip()
            if k in updates:
                out.append(f"{k}={updates[k]}")
                seen.add(k)
                continue
        out.append(line)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


def oauth_url(app_id: str, redirect_uri: str = "https://www.facebook.com/connect/login_success.html") -> str:
    import json
    from urllib.parse import urlencode

    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "scope": ",".join(SCOPES),
        "response_type": "token",
        "display": "page",
        "extras": json.dumps({"setup": {"channel": "IG_API_ONBOARDING"}}, separators=(",", ":")),
    }
    return f"https://www.facebook.com/{API_VERSION}/dialog/oauth?" + urlencode(params)


def exchange_long_lived(app_id: str, app_secret: str, short_token: str) -> str:
    r = httpx.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"Falha ao trocar token: {data}")
    return token


def list_pages(token: str) -> list[dict]:
    r = httpx.get(
        f"{GRAPH}/me/accounts",
        params={
            "access_token": token,
            "fields": "id,name,access_token,instagram_business_account{id,username}",
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json().get("data") or []


def debug(token: str) -> dict:
    app_token = os.environ.get("META_APP_ID", "") + "|" + os.environ.get("META_APP_SECRET", "")
    if "|" in app_token and app_token != "|":
        input_token = token
    else:
        input_token = token
        app_token = token
    r = httpx.get(
        f"{GRAPH}/debug_token",
        params={"input_token": input_token, "access_token": app_token if "|" not in app_token else app_token},
        timeout=60,
    )
    return r.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Configura Page Access Token Meta no .env")
    parser.add_argument("--app-id", default="")
    parser.add_argument("--app-secret", default="")
    parser.add_argument("--short-token", default="", help="User access token de curta duração")
    parser.add_argument("--page-index", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    env = load_env()
    app_id = args.app_id or env.get("META_APP_ID") or os.environ.get("META_APP_ID") or DEFAULT_APP_ID
    app_secret = args.app_secret or env.get("META_APP_SECRET") or os.environ.get("META_APP_SECRET") or ""

    print("=== Meta Page Access Token — @delegadoluizcarlos ===\n")
    print("Scopes necessários:")
    for s in SCOPES:
        print(f"  • {s}")

    if not app_secret:
        app_secret = input("\nMETA_APP_SECRET: ").strip()

    short = args.short_token.strip()
    if not short:
        url = oauth_url(app_id)
        print(f"\n1) Abra esta URL e autorize com a conta que administra a Página:\n\n{url}\n")
        if not args.no_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        print("2) Copie o access_token da URL de redirect (fragmento #access_token=...)")
        short = input("User Access Token (curta duração): ").strip()

    if not short:
        print("Token vazio.", file=sys.stderr)
        return 1

    print("\n→ Trocando por token long-lived…")
    long_token = exchange_long_lived(app_id, app_secret, short)

    print("→ Listando páginas…")
    pages = list_pages(long_token)
    if not pages:
        print(
            "Nenhuma página encontrada. Use a conta Facebook que administra @delegadoluizcarlos.",
            file=sys.stderr,
        )
        return 1

    print("\nPáginas disponíveis:")
    for i, p in enumerate(pages):
        ig = p.get("instagram_business_account") or {}
        print(f"  [{i}] {p.get('name')} (page_id={p.get('id')}, ig=@{ig.get('username', '?')})")

    idx = args.page_index
    if len(pages) > 1 and not args.short_token:
        raw = input(f"\nEscolha a página [0-{len(pages)-1}]: ").strip()
        idx = int(raw) if raw.isdigit() else 0

    page = pages[min(idx, len(pages) - 1)]
    page_token = page.get("access_token")
    if not page_token:
        print("Página sem access_token.", file=sys.stderr)
        return 1

    ig = page.get("instagram_business_account") or {}
    ig_id = ig.get("id") or env.get("IG_USER_ID", "")

    dbg = httpx.get(
        f"{GRAPH}/debug_token",
        params={"input_token": page_token, "access_token": f"{app_id}|{app_secret}"},
        timeout=60,
    ).json()
    scopes = (dbg.get("data") or {}).get("scopes") or []
    print(f"\n✓ Page token — {len(scopes)} permissões")

    updates = {
        "META_ACCESS_TOKEN": page_token,
        "FB_PAGE_ID": page.get("id") or env.get("FB_PAGE_ID", ""),
        "IG_USER_ID": ig_id,
        "META_APP_ID": app_id,
        "META_APP_SECRET": app_secret,
    }
    save_env(updates)
    print(f"\n✓ .env atualizado: FB_PAGE_ID={updates['FB_PAGE_ID']}, IG_USER_ID={ig_id}")
    print("\nRode: python3 scripts/verify_delegado_dashboard.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
