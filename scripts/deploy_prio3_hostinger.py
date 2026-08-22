#!/usr/bin/env python3
"""Deploy do dashboard PRIO3 para Hostinger (naintegracursos.com.br/xxx)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Reutiliza FTPS do deploy Lex
sys.path.insert(0, str(REPO / "scripts"))
from deploy_lex_hostinger import connect, ensure_remote_dir, upload_tree, env_cfg  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy dashboard PRIO3 → Hostinger /xxx/")
    parser.add_argument("--refresh", action="store_true", help="Atualiza dados antes do build")
    parser.add_argument("--skip-build", action="store_true", help="Só envia xxx/ existente")
    args = parser.parse_args()

    if not args.skip_build:
        cmd = [sys.executable, str(REPO / "scripts" / "build_prio3_deploy.py")]
        if args.refresh:
            cmd.append("--refresh")
        subprocess.run(cmd, check=True)

    local = REPO / "xxx"
    if not local.is_dir():
        raise SystemExit(f"Bundle não encontrado: {local}. Rode build_prio3_deploy.py primeiro.")

    cfg = env_cfg()
    remote_dir = cfg.get("FTP_REMOTE_DIR_XXX", cfg.get("FTP_REMOTE_DIR", "./public_html/xxx/")).strip()
    remote_dir = remote_dir.rstrip("/")
    if remote_dir.endswith("/lex"):
        remote_dir = remote_dir.rsplit("/lex", 1)[0] + "/xxx"

    print(f"Origem: {local}")
    print(f"Destino FTP: {remote_dir}")
    ftp = connect(cfg)
    try:
        ensure_remote_dir(ftp, remote_dir)
        n = upload_tree(ftp, local, remote_dir.lstrip("./"))
    finally:
        try:
            ftp.quit()
        except Exception:
            pass

    print(f"\n[OK] {n} arquivo(s) enviados.", flush=True)
    print("Validar: https://www.naintegracursos.com.br/xxx/painel.html", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
