#!/usr/bin/env python3
"""Atualiza assetlinks.json com SHA-256 do certificado Android."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
FP_FILE = MOBILE / "aistudio" / "signing-fingerprints.json"
ASSETLINKS = ROOT / "web" / "site-root" / ".well-known" / "assetlinks.json"
PACKAGE = "br.com.naintegracursos.lex"


def normalize_sha(raw: str) -> str:
    cleaned = re.sub(r"[^0-9a-fA-F]", "", raw.strip())
    if len(cleaned) != 64:
        raise ValueError(f"SHA-256 inválido (64 hex chars): {raw!r}")
    return ":".join(cleaned[i : i + 2].upper() for i in range(0, 64, 2))


def sha_from_keystore(keystore: Path, alias: str, storepass: str) -> str:
    proc = subprocess.run(
        ["keytool", "-list", "-v", "-keystore", str(keystore), "-alias", alias, "-storepass", storepass],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or proc.stdout or "keytool falhou")
    for line in proc.stdout.splitlines():
        if "SHA256:" in line:
            return normalize_sha(line.split(":", 1)[1])
    raise SystemExit("SHA256 não encontrado no output do keytool")


def load_fp_data() -> dict:
    if FP_FILE.exists():
        return json.loads(FP_FILE.read_text(encoding="utf-8"))
    return {"packageName": PACKAGE, "fingerprints": []}


def save_fp_data(data: dict) -> None:
    FP_FILE.parent.mkdir(parents=True, exist_ok=True)
    FP_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_assetlinks(fingerprints: list[str]) -> None:
    payload = [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": PACKAGE,
                "sha256_cert_fingerprints": fingerprints,
            },
        }
    ]
    ASSETLINKS.parent.mkdir(parents=True, exist_ok=True)
    ASSETLINKS.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def add_fingerprint(sha: str) -> None:
    formatted = normalize_sha(sha)
    data = load_fp_data()
    fps: list[str] = data.setdefault("fingerprints", [])
    if formatted not in fps:
        fps.append(formatted)
    data["packageName"] = PACKAGE
    save_fp_data(data)
    write_assetlinks(fps)
    print(f"OK — {len(fps)} fingerprint(s) em {ASSETLINKS}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Atualiza Digital Asset Links para NaIntegra Lex Android")
    parser.add_argument("--add", metavar="SHA256", help="Adicionar SHA-256 (Play Console → App integrity)")
    parser.add_argument("--from-keystore", type=Path, metavar="FILE", help="Extrair SHA-256 de keystore local")
    parser.add_argument("--alias", default="naintegra-lex", help="Alias do keystore (default: naintegra-lex)")
    parser.add_argument("--storepass", default="", help="Senha do keystore")
    parser.add_argument("--list", action="store_true", help="Listar fingerprints e regenerar assetlinks.json")
    args = parser.parse_args()

    if args.list:
        data = load_fp_data()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        write_assetlinks(data.get("fingerprints", []))
        return 0

    if args.from_keystore:
        storepass = args.storepass or input("Senha do keystore: ")
        sha = sha_from_keystore(args.from_keystore, args.alias, storepass)
        add_fingerprint(sha)
        return 0

    if args.add:
        add_fingerprint(args.add)
        return 0

    parser.print_help()
    print("\nPlay Console: Configuração → Integridade do app → Certificado de assinatura do app")
    return 1


if __name__ == "__main__":
    sys.exit(main())
