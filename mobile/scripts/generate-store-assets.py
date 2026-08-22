#!/usr/bin/env python3
"""Gera feature graphic (1024×500) e ícone 512 para Google Play.

As capturas de tela são geradas por export-play-screenshots.py, que renderiza o
repositório local em viewports de aparelho. Este script não captura da produção
para não congelar na loja uma versão desatualizada da interface.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
OUT = MOBILE / "store-assets" / "generated"
ICON = ROOT / "web" / "lex" / "icons" / "icon-512.png"


def ensure_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        return
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pillow", "-q"], check=True)


def make_feature_graphic() -> Path:
    from PIL import Image, ImageDraw, ImageFont

    OUT.mkdir(parents=True, exist_ok=True)
    w, h = 1024, 500
    img = Image.new("RGB", (w, h), "#faf8f4")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w, 8], fill="#9a6e00")
    draw.rectangle([0, h - 8, w, h], fill="#9a6e00")
    draw.rectangle([72, 96, 76, h - 96], fill="#e8dcc4")

    if ICON.exists():
        logo = Image.open(ICON).convert("RGBA")
        logo = logo.resize((188, 188), Image.Resampling.LANCZOS)
        img.paste(logo, (84, (h - 188) // 2), logo)

    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 54)
        font_features = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 26)
        font_tag = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 30)
        font_note = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    except OSError:
        font_title = ImageFont.load_default()
        font_features = font_title
        font_tag = font_title
        font_note = font_title

    text_x = 300
    draw.text((text_x, 148), "NaIntegra Lex", fill="#1a1a1a", font=font_title)
    draw.text(
        (text_x, 228),
        "Lei seca · Jurisprudência · Flashcards · Questões",
        fill="#5a5348",
        font=font_features,
    )
    draw.text((text_x, 282), "Concursos públicos · 100% grátis", fill="#9a6e00", font=font_tag)
    draw.text(
        (text_x, 330),
        "Sem assinatura, sem anúncios · atualizado semanalmente",
        fill="#5a5348",
        font=font_note,
    )

    out = OUT / "feature-graphic-1024x500.png"
    img.save(out, "PNG", optimize=True)
    return out


def make_icon_copy() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "icon-512-play-store.png"
    if ICON.exists():
        from shutil import copy2
        copy2(ICON, out)
    return out


def main() -> int:
    print("==> Feature graphic + ícone")
    ensure_pillow()
    fg = make_feature_graphic()
    ic = make_icon_copy()
    print(f"  {fg}")
    print(f"  {ic}")

    shots = sorted((OUT / "phone").glob("screenshot-*.png"))
    if shots:
        print(f"==> Capturas já geradas: {len(shots)} em {OUT / 'phone'}")
    else:
        print("==> Capturas ausentes — rode: npm run play:screenshots")

    print(f"\nAssets em: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
