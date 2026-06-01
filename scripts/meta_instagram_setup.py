#!/usr/bin/env python3
"""Configura permissões Instagram (Facebook Login) e renova Page Access Token.

Uso:
  python3 scripts/meta_instagram_setup.py check
  python3 scripts/meta_instagram_setup.py url          # URL OAuth com scopes IG
  python3 scripts/meta_instagram_setup.py token --short-token TOKEN
  python3 scripts/meta_instagram_setup.py test         # testa token atual no .env
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

# Instagram API com Facebook Login (Page Token) — dashboard @delegadoluizcarlos
SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "instagram_basic",
    "instagram_content_publish",
    "instagram_manage_comments",
    "instagram_manage_insights",
    "ads_read",
    "business_management",
]

NEEDED_IG = {"instagram_basic", "instagram_content_publish", "pages_read_engagement", "pages_show_list"}


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
    seen: set[str] = set()
    out: list[str] = []
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


def app_token(app_id: str, app_secret: str) -> str:
    return f"{app_id}|{app_secret}"


def oauth_url(app_id: str) -> str:
    """URL recomendada pela Meta para onboarding Instagram API + Facebook Login."""
    params = {
        "client_id": app_id,
        "redirect_uri": "https://www.facebook.com/connect/login_success.html",
        "response_type": "token",
        "display": "page",
        "scope": ",".join(SCOPES),
        "extras": json.dumps({"setup": {"channel": "IG_API_ONBOARDING"}}, separators=(",", ":")),
    }
    return f"https://www.facebook.com/{API_VERSION}/dialog/oauth?" + urlencode(params)


def cmd_check(env: dict[str, str]) -> int:
    app_id = env.get("META_APP_ID", "")
    app_secret = env.get("META_APP_SECRET", "")
    print("=== Diagnóstico Meta / Instagram ===\n")
    if not app_id:
        print("✗ META_APP_ID ausente no .env")
        return 1
    if not app_secret:
        print("✗ META_APP_SECRET ausente — copie em developers.facebook.com → App → Configurações → Básico")
        return 1

    tok = app_token(app_id, app_secret)
    r = httpx.get(f"{GRAPH}/{app_id}", params={"fields": "name", "access_token": tok}, timeout=30)
    if r.status_code != 200:
        err = r.json().get("error", {})
        print(f"✗ App ID/Secret inválidos: {err.get('message', r.text)}")
        print("\n  → Abra Configurações → Básico → Chave Secreta do Aplicativo → Mostrar")
        print("  → Atualize META_APP_SECRET no .env")
        return 1

    print(f"✓ App válido: {r.json().get('name')} (ID {app_id})")
    print("\nPermissões necessárias (OAuth scopes):")
    for s in SCOPES:
        mark = "★" if s in NEEDED_IG or s.startswith("instagram_") else " "
        print(f"  {mark} {s}")

    print("\n--- Painel Meta (faça manualmente se permissões não aparecem) ---")
    print("1. Adicionar produto → Instagram + Facebook Login for Business")
    print("2. Casos de uso → Personalizar → marcar instagram_basic e instagram_content_publish")
    print("3. Revisão do app → Permissões e recursos → Solicitar acesso avançado")
    print("4. Funções do app → sua conta Facebook como Administrador")
    print("\n--- OAuth (gera token de teste) ---")
    url = oauth_url(app_id)
    print(url)
    print("\nDepois: python3 scripts/meta_instagram_setup.py token --short-token SEU_TOKEN")
    return 0


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
    token = r.json().get("access_token")
    if not token:
        raise RuntimeError(f"Falha ao trocar token: {r.json()}")
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


def cmd_token(env: dict[str, str], short: str, page_index: int) -> int:
    app_id = env.get("META_APP_ID", "")
    app_secret = env.get("META_APP_SECRET", "")
    if not app_secret:
        print("META_APP_SECRET ausente.", file=sys.stderr)
        return 1

    print("→ Token long-lived…")
    long_token = exchange_long_lived(app_id, app_secret, short)

    dbg = httpx.get(
        f"{GRAPH}/debug_token",
        params={"input_token": long_token, "access_token": app_token(app_id, app_secret)},
        timeout=60,
    ).json()
    scopes = set((dbg.get("data") or {}).get("scopes") or [])
    missing = NEEDED_IG - scopes
    if missing:
        print(f"⚠ Token sem permissões IG: {', '.join(sorted(missing))}")
        print("  Refaça OAuth marcando todas as permissões Instagram no consentimento.")
    else:
        print("✓ Permissões IG básicas presentes no user token")

    pages = list_pages(long_token)
    if not pages:
        print("Nenhuma Página Facebook encontrada.", file=sys.stderr)
        return 1

    print("\nPáginas:")
    for i, p in enumerate(pages):
        ig = p.get("instagram_business_account") or {}
        print(f"  [{i}] {p.get('name')} — IG @{ig.get('username', '?')}")

    page = pages[min(page_index, len(pages) - 1)]
    page_token = page.get("access_token")
    if not page_token:
        print("Página sem access_token.", file=sys.stderr)
        return 1

    ig = page.get("instagram_business_account") or {}
    dbg2 = httpx.get(
        f"{GRAPH}/debug_token",
        params={"input_token": page_token, "access_token": app_token(app_id, app_secret)},
        timeout=60,
    ).json()
    pscopes = (dbg2.get("data") or {}).get("scopes") or []
    print(f"\n✓ Page token — {len(pscopes)} permissões")

    updates = {
        "META_ACCESS_TOKEN": page_token,
        "FB_PAGE_ID": page.get("id") or env.get("FB_PAGE_ID", ""),
        "IG_USER_ID": ig.get("id") or env.get("IG_USER_ID", ""),
        "META_APP_ID": app_id,
        "META_APP_SECRET": app_secret,
    }
    save_env(updates)
    print(f"✓ .env atualizado — FB_PAGE_ID={updates['FB_PAGE_ID']}, IG_USER_ID={updates['IG_USER_ID']}")
    return 0


def cmd_test(env: dict[str, str]) -> int:
    token = env.get("META_ACCESS_TOKEN", "")
    app_id = env.get("META_APP_ID", "")
    app_secret = env.get("META_APP_SECRET", "")
    ig_id = env.get("IG_USER_ID", "")
    if not token:
        print("META_ACCESS_TOKEN vazio")
        return 1

    r = httpx.get(
        f"{GRAPH}/debug_token",
        params={"input_token": token, "access_token": app_token(app_id, app_secret)},
        timeout=30,
    )
    data = (r.json().get("data") or {})
    if not data.get("is_valid"):
        print(f"✗ Token inválido/expirado: {(r.json().get('error') or {}).get('message', r.text)}")
        print("  Rode: python3 scripts/meta_instagram_setup.py url")
        return 1

    scopes = set(data.get("scopes") or [])
    print(f"✓ Token válido — expira {data.get('expires_at')}")
    missing = NEEDED_IG - scopes
    if missing:
        print(f"⚠ Faltam: {', '.join(sorted(missing))}")
    else:
        print("✓ Permissões IG OK")

    if ig_id.isdigit():
        mr = httpx.get(
            f"{GRAPH}/{ig_id}/media",
            params={"access_token": token, "fields": "id,caption", "limit": 1},
            timeout=30,
        )
        if mr.status_code == 200:
            n = len(mr.json().get("data") or [])
            print(f"✓ instagram_basic — listou {n} post(s)")
        else:
            err = mr.json().get("error", {})
            print(f"✗ instagram_basic — {err.get('message', mr.text)[:200]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup Instagram permissions + Page token")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="Valida app secret e mostra checklist")
    p_url = sub.add_parser("url", help="Imprime/abre URL OAuth")
    p_url.add_argument("--open", action="store_true")
    p_tok = sub.add_parser("token", help="Converte short token → Page token no .env")
    p_tok.add_argument("--short-token", default=os.environ.get("META_SHORT_TOKEN", ""))
    p_tok.add_argument("--page-index", type=int, default=0)
    sub.add_parser("test", help="Testa META_ACCESS_TOKEN atual")

    args = parser.parse_args()
    env = load_env()

    if args.cmd == "check":
        return cmd_check(env)
    if args.cmd == "url":
        app_id = env.get("META_APP_ID", "")
        if not app_id:
            print("META_APP_ID ausente", file=sys.stderr)
            return 1
        url = oauth_url(app_id)
        print(url)
        if args.open:
            webbrowser.open(url)
        return 0
    if args.cmd == "token":
        short = args.short_token.strip()
        if not short:
            print("Informe --short-token ou META_SHORT_TOKEN no ambiente.", file=sys.stderr)
            return 1
        return cmd_token(env, short, args.page_index)
    if args.cmd == "test":
        return cmd_test(env)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
