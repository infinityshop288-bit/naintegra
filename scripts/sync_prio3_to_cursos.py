#!/usr/bin/env python3
"""Sincroniza o bundle xxx/ (dashboard PRIO3) → public/xxx/ (naintegracursos)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
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


def build_bundle(refresh: bool) -> Path:
    repo = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, str(repo / "scripts" / "build_prio3_deploy.py")]
    if refresh:
        cmd.append("--refresh")
    run(cmd, cwd=repo)
    out = repo / "xxx"
    if not out.is_dir():
        raise SystemExit(f"Bundle não gerado: {out}")
    return out


def sync_to_cursos(src: Path, cursos: Path) -> int:
    dst = cursos / "public" / "xxx"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".DS_Store"))
    return sum(1 for _ in dst.rglob("*") if _.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description="Build + sync dashboard PRIO3 para naintegracursos")
    parser.add_argument("--cursos-dir", default=default_cursos_dir())
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Atualiza macro/análise/opções + snapshots API")
    parser.add_argument("--skip-build", action="store_true", help="Usa xxx/ já existente")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    src = repo / "xxx"
    if not args.skip_build:
        src = build_bundle(args.refresh)

    cursos = Path(args.cursos_dir).expanduser()
    if not (cursos / ".git").is_dir():
        raise SystemExit(f"Repo naintegracursos não encontrado: {cursos}")

    n = sync_to_cursos(src, cursos)
    print(f"Sincronizado → {cursos / 'public' / 'xxx'} ({n} arquivos)", flush=True)

    if not args.push:
        return 0

    run(["git", "add", "public/xxx"], cwd=cursos)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cursos,
        capture_output=True,
        text=True,
        check=True,
    )
    if not status.stdout.strip():
        print("Sem alterações em public/xxx", flush=True)
        return 0

    msg = os.environ.get("SYNC_COMMIT_MESSAGE", "Publica dashboard PRIO3 em public/xxx")
    run(["git", "commit", "-m", msg], cwd=cursos)
    run(["git", "push", "origin", "HEAD:main"], cwd=cursos)
    print("[OK] Push em naintegracursos/main — Hostinger publica em /xxx/", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
