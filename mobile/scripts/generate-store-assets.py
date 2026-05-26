#!/usr/bin/env python3
"""Gera feature graphic (1024×500) e capturas (1080×1920) para Google Play."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
OUT = MOBILE / "store-assets" / "generated"
ICON = ROOT / "web" / "lex" / "icons" / "icon-512.png"
LEX_URL = "https://www.naintegracursos.com.br/lex/"


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
    draw.text((text_x, 282), "Concursos públicos", fill="#9a6e00", font=font_tag)
    draw.text(
        (text_x, 330),
        "Material atualizado semanalmente · ideal no transporte",
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


def screenshots_playwright() -> list[Path]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    shots: list[Path] = []
    routes = [
        ("01-inicio", "#/"),
        ("02-lei-seca", "#/lei-seca"),
        ("03-flashcards", "#/flashcards"),
        ("04-jurisprudencia", "#/jurisprudencia"),
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        for name, route in routes:
            page.goto(f"{LEX_URL}{route}", wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(2500)
            path = OUT / f"screenshot-{name}-1080x1920.png"
            page.screenshot(path=str(path), full_page=False)
            shots.append(path)
            print(f"  captura: {path.name}")
        browser.close()
    return shots


def main() -> int:
    print("==> Feature graphic + ícone")
    ensure_pillow()
    fg = make_feature_graphic()
    ic = make_icon_copy()
    print(f"  {fg}")
    print(f"  {ic}")

    print("==> Capturas de tela (Playwright → site produção)")
    try:
        shots = screenshots_playwright()
        print(f"  {len(shots)} captura(s)")
    except Exception as exc:
        print(f"[AVISO] Capturas automáticas falharam: {exc}")
        print("  Faça capturas manualmente no emulador AI Studio (1080×1920).")

    print(f"\nAssets em: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
