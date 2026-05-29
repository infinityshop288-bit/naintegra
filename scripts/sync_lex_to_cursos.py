#!/usr/bin/env python3
"""Sincroniza web/lex (naintegra) → public/lex (naintegracursos) e faz push."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def default_cursos_dir() -> str:
    candidates = [
        Path(__file__).resolve().parents[1].parent / "naintegracursos",
        Path(__file__).resolve().parents[2].parent / "naintegracursos",
    ]
    for p in candidates:
        if (p / ".git").is_dir():
            return str(p)
    return str(candidates[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cursos-dir",
        default=default_cursos_dir(),
        help="Caminho do clone infinityshop288-bit/naintegracursos",
    )
    parser.add_argument("--push", action="store_true", help="git commit + push no repo cursos")
    parser.add_argument("--message", default="Atualiza NaIntegra Lex em public/lex")
    args = parser.parse_args()

    naintegra = Path(__file__).resolve().parents[1]
    src = naintegra / "web" / "lex"
    cursos = Path(args.cursos_dir).expanduser()
    dst = cursos / "public" / "lex"

    if not src.is_dir():
        raise SystemExit(f"Origem não encontrada: {src}")
    if not (cursos / ".git").is_dir():
        raise SystemExit(f"Repo naintegracursos não encontrado: {cursos}")

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".DS_Store"))
    print(f"Sincronizado → {dst} ({sum(1 for _ in dst.rglob('*') if _.is_file())} arquivos)")

    if not args.push:
        return

    run(["git", "add", "public/lex"], cwd=cursos)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=cursos, capture_output=True, text=True, check=True)
    if not status.stdout.strip():
        print("Nada a commitar.")
        return
    run(["git", "commit", "-m", args.message], cwd=cursos)
    run(["git", "push", "origin", "HEAD"], cwd=cursos)
    print("Push concluído — Hostinger/Lovable deve publicar /lex no próximo deploy.")


if __name__ == "__main__":
    main()
