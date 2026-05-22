"""CLI: normalização do corpus norma_chunks (delega a scripts/normalize_norma_corpus.py)."""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "normalize_norma_corpus.py"
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
