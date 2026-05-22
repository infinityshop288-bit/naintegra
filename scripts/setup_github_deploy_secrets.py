#!/usr/bin/env python3
"""Grava secrets de deploy FTP/SSH no repositório GitHub (Actions)."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "infinityshop288-bit/naintegra")
SECRET_MAP = {
    "FTP_SERVER": "FTP_SERVER",
    "FTP_USERNAME": "FTP_USERNAME",
    "FTP_PASSWORD": "FTP_PASSWORD",
    "FTP_PORT": "FTP_PORT",
    "FTP_REMOTE_DIR": "FTP_REMOTE_DIR",
    "SSH_HOST": "SSH_HOST",
    "SSH_USERNAME": "SSH_USERNAME",
    "SSH_PRIVATE_KEY": "SSH_PRIVATE_KEY",
    "SSH_PORT": "SSH_PORT",
    "SSH_REMOTE_DIR": "SSH_REMOTE_DIR",
}


def git_token() -> str:
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        text=True,
        capture_output=True,
        check=True,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("Token GitHub não encontrado (git credential).")


def api(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    url = f"https://api.github.com/repos/{REPO}{path}"
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode()
        return json.loads(body) if body else {}


def ensure_pynacl():
    try:
        import nacl  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pynacl", "-q"])


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    from nacl import encoding, public

    key = public.PublicKey(public_key_b64.encode(), encoding.Base64Encoder())
    sealed = public.SealedBox(key).encrypt(secret_value.encode())
    return base64.b64encode(sealed).decode()


def load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Configura secrets de deploy Lex no GitHub Actions")
    parser.add_argument("--from-env", default=".env.deploy", help="Arquivo .env.deploy com credenciais")
    args = parser.parse_args()

    env = load_env_file(Path(args.from_env))
    if not env:
        print(f"Arquivo {args.from_env} não encontrado ou vazio.", file=sys.stderr)
        print("Copie .env.deploy.example → .env.deploy e preencha FTP ou SSH.", file=sys.stderr)
        raise SystemExit(1)

    token = git_token()
    ensure_pynacl()
    pub = api("GET", "/actions/secrets/public-key", token)

    uploaded = 0
    for env_key, secret_name in SECRET_MAP.items():
        value = env.get(env_key, "").strip()
        if not value:
            continue
        encrypted = encrypt_secret(pub["key"], value)
        api(
            "PUT",
            f"/actions/secrets/{secret_name}",
            token,
            {"encrypted_value": encrypted, "key_id": pub["key_id"]},
        )
        print(f"✓ {secret_name}")
        uploaded += 1

    if uploaded == 0:
        raise SystemExit("Nenhum secret preenchido em .env.deploy")

    print(f"\n{uploaded} secret(s) gravados em {REPO}.")
    print("Dispare o deploy: GitHub → Actions → Deploy Lex → Run workflow")


if __name__ == "__main__":
    main()
