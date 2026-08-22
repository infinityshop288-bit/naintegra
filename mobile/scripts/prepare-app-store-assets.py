#!/usr/bin/env python3
"""Prepara capturas 1290×2796 e ícone 1024×1024 para App Store."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
SRC = MOBILE / "store-assets" / "generated" / "phone"
OUT = MOBILE / "store-assets" / "generated" / "app-store"
ICON_SRC = MOBILE / "store-assets" / "generated" / "icon-512-play-store.png"
ICON_FALLBACK = ROOT / "web" / "lex" / "icons" / "icon-512.png"


def ensure_pillow():
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pillow", "-q"], check=True)


def main() -> None:
    from PIL import Image

    ensure_pillow()
    OUT.mkdir(parents=True, exist_ok=True)

    shots = sorted(SRC.glob("screenshot-*.png")) if SRC.is_dir() else []
    if not shots:
        shots = sorted((MOBILE / "store-assets" / "generated").glob("screenshot-*.png"))
    if len(shots) < 3:
        raise SystemExit("Gere capturas antes: cd mobile && npm run play:screenshots")

    sizes = (
        ("iphone-67", 1290, 2796),
        ("iphone-65", 1284, 2778),
        ("ipad-13", 2048, 2732),
    )
    for i, src in enumerate(shots[:5], start=1):
        img = Image.open(src).convert("RGB")
        for prefix, w, h in sizes:
            resized = img.resize((w, h), Image.Resampling.LANCZOS)
            out = OUT / f"{prefix}-{i:02d}.png"
            resized.save(out, "PNG", optimize=True)
            print(f"  {out.name}")

    icon_path = ICON_SRC if ICON_SRC.exists() else ICON_FALLBACK
    if not icon_path.exists():
        raise SystemExit("Ícone não encontrado")
    icon = Image.open(icon_path).convert("RGBA")
    icon = icon.resize((1024, 1024), Image.Resampling.LANCZOS)
    bg = Image.new("RGB", (1024, 1024), (250, 248, 244))
    bg.paste(icon, ((1024 - icon.width) // 2, (1024 - icon.height) // 2), icon)
    icon_out = OUT / "icon-1024.png"
    bg.save(icon_out, "PNG", optimize=True)
    print(f"  {icon_out.name}")
    print(f"Salvo em {OUT}")


if __name__ == "__main__":
    main()
