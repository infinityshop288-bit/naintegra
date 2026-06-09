#!/usr/bin/env python3
"""Clona ou atualiza o repositório Marketing Digital para DELEGADO_MARKETING_REPO_PATH."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_REPO = REPO / "data" / "delegado" / "marketing_digital" / "repo"
DEFAULT_URL = "https://github.com/infinityshop288-bit/marketingdigital.git"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        default=os.environ.get("DELEGADO_MARKETING_REPO_URL", "").strip() or DEFAULT_URL,
        help="URL git do repo Marketing Digital",
    )
    parser.add_argument(
        "--path",
        default=os.environ.get("DELEGADO_MARKETING_REPO_PATH", "").strip()
        or str(DEFAULT_REPO),
    )
    args = parser.parse_args()
    dest = Path(args.path).expanduser().resolve()

    if not args.url:
        print(
            "Informe --url ou DELEGADO_MARKETING_REPO_URL (ex.: https://github.com/org/Marketing-Digital.git)",
            file=sys.stderr,
        )
        return 1

    if dest.exists() and (dest / ".git").is_dir():
        subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"], check=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", args.url, str(dest)], check=True)

    print(f"OK: {dest}")
    print(f"Exporte: DELEGADO_MARKETING_REPO_PATH={dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
