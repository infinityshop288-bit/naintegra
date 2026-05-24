#!/usr/bin/env python3
"""Sincroniza web/site-root → public/ (raiz do site naintegracursos)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cursos-dir",
        default=str(Path(__file__).resolve().parents[2].parent / "GitHub" / "naintegracursos"),
        help="Clone do repo naintegracursos",
    )
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--message", default="Publica .well-known/assetlinks.json (NaIntegra Lex Android)")
    args = parser.parse_args()

    naintegra = Path(__file__).resolve().parents[1]
    src = naintegra / "web" / "site-root"
    cursos = Path(args.cursos_dir).expanduser()
    dst_root = cursos / "public"

    if not src.is_dir():
        raise SystemExit(f"Origem não encontrada: {src}")
    if not (cursos / ".git").is_dir():
        raise SystemExit(f"Repo naintegracursos não encontrado: {cursos}")

    copied = 0
    for item in src.rglob("*"):
        if not item.is_file() or item.name == ".DS_Store":
            continue
        rel = item.relative_to(src)
        target = dst_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        copied += 1
        print(f"  {rel}")

    print(f"Sincronizado {copied} arquivo(s) → {dst_root}")

    if not args.push:
        print("Use --push para commit + push no repo cursos.")
        return

    run(["git", "add", "public/.well-known"], cwd=cursos)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cursos,
        capture_output=True,
        text=True,
        check=True,
    )
    if not status.stdout.strip():
        print("Nada a commitar.")
        return
    run(["git", "commit", "-m", args.message], cwd=cursos)
    run(["git", "push", "origin", "HEAD"], cwd=cursos)
    print("Push concluído — assetlinks.json deve ficar em https://www.naintegracursos.com.br/.well-known/assetlinks.json")


if __name__ == "__main__":
    main()
