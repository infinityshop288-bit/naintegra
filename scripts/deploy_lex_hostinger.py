#!/usr/bin/env python3
"""Deploy NaIntegra Lex (ou site completo) no Hostinger via FTPS."""
from __future__ import annotations

import argparse
import ftplib
import os
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
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


def env_cfg() -> dict[str, str]:
    cfg = load_env(ROOT / ".env.deploy")
    for key in (
        "FTP_SERVER",
        "FTP_USERNAME",
        "FTP_PASSWORD",
        "FTP_PORT",
        "FTP_REMOTE_DIR",
    ):
        if os.environ.get(key):
            cfg[key] = os.environ[key]
    return cfg


class ImplicitFTPS(ftplib.FTP_TLS):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._prot_p = False

    def storbinary(self, cmd, fp, blocksize=8192, callback=None, rest=None):
        if not self._prot_p:
            self.prot_p()
            self._prot_p = True
        return super().storbinary(cmd, fp, blocksize, callback, rest)


def connect(cfg: dict[str, str]) -> ftplib.FTP:
    host = cfg.get("FTP_SERVER", "").strip()
    user = cfg.get("FTP_USERNAME", "").strip()
    password = cfg.get("FTP_PASSWORD", "").strip()
    port = int(cfg.get("FTP_PORT", "21") or "21")
    if not host or not user or not password:
        raise SystemExit(
            "Credenciais FTP ausentes.\n"
            "Copie .env.deploy.example → .env.deploy e preencha FTP_SERVER, FTP_USERNAME, FTP_PASSWORD.\n"
            "Hostinger: hPanel → Sites → Arquivos → Detalhes FTP."
        )
    ftp = ImplicitFTPS()
    ftp.connect(host, port, timeout=60)
    ftp.login(user, password)
    ftp.set_pasv(True)
    return ftp


def ensure_remote_dir(ftp: ftplib.FTP, remote_dir: str) -> None:
    parts = [p for p in remote_dir.replace("\\", "/").split("/") if p and p != "."]
    path = ""
    for part in parts:
        path = f"{path}/{part}" if path else part
        try:
            ftp.cwd(path)
        except ftplib.error_perm:
            ftp.mkd(path)
            ftp.cwd(path)


def upload_tree(ftp: ftplib.FTP, local: Path, remote_prefix: str = ".") -> int:
    count = 0
    for item in sorted(local.rglob("*")):
        if item.name == ".DS_Store":
            continue
        rel = item.relative_to(local).as_posix()
        remote_path = f"{remote_prefix}/{rel}" if remote_prefix not in (".", "") else rel
        if item.is_dir():
            try:
                ftp.mkd(remote_path)
            except ftplib.error_perm:
                pass
            continue
        remote_parent = "/".join(remote_path.split("/")[:-1])
        if remote_parent:
            ensure_remote_dir(ftp, remote_parent)
        with item.open("rb") as fp:
            ftp.storbinary(f"STOR {remote_path}", fp)
        count += 1
        if count % 25 == 0:
            print(f"  {count} arquivo(s)...", flush=True)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy Lex/site para Hostinger (FTPS)")
    parser.add_argument(
        "--source",
        choices=("lex", "dist"),
        default="lex",
        help="lex = só NaIntegra Lex; dist = build completo do naintegracursos",
    )
    parser.add_argument(
        "--cursos-dir",
        default=str(ROOT.parent / "naintegracursos"),
        help="Repo naintegracursos (para --source dist)",
    )
    args = parser.parse_args()

    cfg = env_cfg()
    remote_dir = cfg.get("FTP_REMOTE_DIR", "./public_html/lex/").strip()
    remote_dir = remote_dir.rstrip("/")

    if args.source == "lex":
        subprocess_run_publish = __import__("subprocess").run
        subprocess_run_publish(["bash", str(ROOT / "scripts" / "publish_lex_static.sh")], check=True)
        local = ROOT / "lex"
    else:
        cursos = Path(args.cursos_dir).expanduser()
        subprocess = __import__("subprocess")
        subprocess.run(["npm", "ci"], cwd=cursos, check=True)
        subprocess.run(["npm", "run", "build"], cwd=cursos, check=True)
        local = cursos / "dist"
        remote_dir = cfg.get("FTP_REMOTE_DIR", "./public_html/").strip().rstrip("/")
        if remote_dir.endswith("/lex"):
            remote_dir = remote_dir.rsplit("/lex", 1)[0] or "."

    if not local.is_dir():
        raise SystemExit(f"Pasta local não encontrada: {local}")

    print(f"Origem: {local}")
    print(f"Destino FTP: {remote_dir}")
    ftp = connect(cfg)
    try:
        ensure_remote_dir(ftp, remote_dir)
        if args.source == "lex":
            target = f"{remote_dir}/lex" if not remote_dir.endswith("/lex") else remote_dir
            ensure_remote_dir(ftp, target)
            n = upload_tree(ftp, local, target if not target.startswith("./") else target.lstrip("./"))
        else:
            n = upload_tree(ftp, local, remote_dir if not remote_dir.startswith("./") else remote_dir.lstrip("./"))
    finally:
        try:
            ftp.quit()
        except Exception:
            pass

    print(f"\n[OK] {n} arquivo(s) enviados.", flush=True)
    print("Validar: https://www.naintegracursos.com.br/lex/js/offline-store.js", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
