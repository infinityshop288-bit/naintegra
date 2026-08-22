#!/usr/bin/env python3
"""Resolve os 2 bloqueios finais: privacidade + conformidade de exportação."""
import subprocess
import sys
from pathlib import Path

MOBILE = Path(__file__).resolve().parents[1]
subprocess.run(
    [sys.executable, str(MOBILE / "scripts/complete-app-store-review.py"), "--blockers-only"],
    check=False,
)
