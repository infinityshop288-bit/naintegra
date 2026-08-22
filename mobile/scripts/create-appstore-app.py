#!/usr/bin/env python3
"""Cria o app NaIntegra Lex no App Store Connect via API (requer chave .p8)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import jwt
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "pyjwt", "cryptography", "requests", "-q"], check=True)
    import jwt
    import requests

BUNDLE_ID = "br.com.naintegracursos.lex"
APP_NAME = "NaIntegra Lex"
SKU = "naintegra-lex"
TEAM_ID = os.environ.get("APPLE_TEAM_ID", "D7323783Z5")
API_BASE = "https://api.appstoreconnect.apple.com/v1"


def key_path() -> Path:
    key_id = os.environ.get("APPLE_API_KEY_ID", "").strip()
    path = os.environ.get("APPLE_API_KEY_PATH", "").strip()
    if not path and key_id:
        path = str(Path.home() / ".appstoreconnect" / "private_keys" / f"AuthKey_{key_id}.p8")
    if not path or not Path(path).expanduser().exists():
        raise SystemExit(
            "Defina APPLE_API_KEY_ID, APPLE_API_ISSUER_ID e APPLE_API_KEY_PATH.\n"
            "Crie em App Store Connect → Usuários e Acesso → Integrações → Chaves de API."
        )
    return Path(path).expanduser()


def token() -> str:
    key_id = os.environ["APPLE_API_KEY_ID"].strip()
    issuer = os.environ["APPLE_API_ISSUER_ID"].strip()
    with open(key_path(), "r", encoding="utf-8") as f:
        private_key = f.read()
    now = int(time.time())
    payload = {"iss": issuer, "iat": now, "exp": now + 1200, "aud": "appstoreconnect-v1"}
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": key_id})


def api(method: str, path: str, body: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token()}", "Content-Type": "application/json"}
    url = f"{API_BASE}{path}"
    resp = requests.request(method, url, headers=headers, json=body, timeout=60)
    if resp.status_code >= 400:
        raise SystemExit(f"{method} {path} → {resp.status_code}: {resp.text[:800]}")
    return resp.json() if resp.text else {}


def main() -> None:
    for var in ("APPLE_API_KEY_ID", "APPLE_API_ISSUER_ID"):
        if not os.environ.get(var, "").strip():
            raise SystemExit(f"Variável ausente: {var}")

    apps = api("GET", f"/apps?filter[bundleId]={BUNDLE_ID}")
    if apps.get("data"):
        print(f"[OK] App já existe: {apps['data'][0]['id']}")
        return

    bundle_apps = api("GET", f"/bundleIds?filter[identifier]={BUNDLE_ID}")
    if bundle_apps.get("data"):
        bundle_id = bundle_apps["data"][0]["id"]
        print(f"[OK] Bundle ID existente: {bundle_id}")
    else:
        created = api(
            "POST",
            "/bundleIds",
            {
                "data": {
                    "type": "bundleIds",
                    "attributes": {
                        "identifier": BUNDLE_ID,
                        "name": APP_NAME,
                        "platform": "IOS",
                    },
                }
            },
        )
        bundle_id = created["data"]["id"]
        print(f"[OK] Bundle ID criado: {bundle_id}")

    created_app = api(
        "POST",
        "/apps",
        {
            "data": {
                "type": "apps",
                "attributes": {
                    "bundleId": BUNDLE_ID,
                    "name": APP_NAME,
                    "sku": SKU,
                    "primaryLocale": "pt-BR",
                },
                "relationships": {
                    "bundleId": {"data": {"type": "bundleIds", "id": bundle_id}}
                },
            }
        },
    )
    print(f"[OK] App criado no App Store Connect: {created_app['data']['id']}")
    print(json.dumps(created_app["data"]["attributes"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
