#!/usr/bin/env python3
"""Exporta respostas das APIs do live_server.py para JSON estático (deploy Hostinger)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "prio3_analysis"
OUT = ROOT / "api"

ENDPOINTS = (
    ("live", "get_live"),
    ("signal", "signal"),
    ("options", "option_chain"),
    ("daytrade", "daytrade"),
    ("tenx", "tenx"),
    ("multiquotes", "multiquotes"),
    ("radar", "radar"),
)


def main() -> int:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    import live_server as ls  # noqa: WPS433

    OUT.mkdir(parents=True, exist_ok=True)
    meta: dict[str, str] = {}
    for name, fn_name in ENDPOINTS:
        fn = getattr(ls, fn_name)
        print(f"  api/{name}.json ...", flush=True)
        try:
            data = fn()
            (OUT / f"{name}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            meta[name] = "ok"
        except Exception as e:  # noqa: BLE001
            meta[name] = f"erro: {e}"
            print(f"    aviso: {e}", flush=True)
    (OUT / "_export_meta.json").write_text(
        json.dumps({"endpoints": meta}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[OK] snapshots em {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
