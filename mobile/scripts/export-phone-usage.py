#!/usr/bin/env python3
"""Duas imagens do NaIntegra Lex em uso no celular (mockup + toque)."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "mobile" / "store-assets" / "generated" / "phone-usage"
DOCS = Path.home() / "Documents" / "NaIntegra-Lex-GooglePlay" / "phone-usage"
BASE = "http://127.0.0.1:8765/web/lex/index.html?promo=1"

SCENES = [
    ("01-flashcards", "#/flashcards", 195, 620, "Flashcards"),
    ("02-lei-seca", "#/lei-seca", 195, 480, "Lei seca"),
]


def ensure_deps() -> None:
    for pkg in ("pillow", "playwright"):
        try:
            __import__(pkg)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def start_server() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "preview" / "serve_preview.py"), "--port", "8765", "--open", "none"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)
    return proc


def clean_ui(page) -> None:
    page.evaluate(
        """() => {
          document.querySelectorAll('#auth-modal-backdrop, .auth-modal-backdrop').forEach(el => el.remove());
          document.getElementById('lex-watermark')?.remove();
        }"""
    )


def touch_overlay(path: Path, x: int, y: int, label: str) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    r = 28
    draw.ellipse([x - r, y - r, x + r, y + r], fill=(154, 110, 0, 90), outline=(255, 255, 255, 200), width=3)
    draw.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(255, 255, 255, 180))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    tw = draw.textlength(label, font=font)
    draw.rounded_rectangle([24, 24, 24 + tw + 24, 64], radius=12, fill=(26, 26, 26, 210))
    draw.text((36, 32), label, fill="#ffffff", font=font)
    out = path.with_name(path.stem + "-touch.png")
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out


def phone_mockup(screenshot: Path, out: Path) -> Path:
    from PIL import Image, ImageDraw

    screen = Image.open(screenshot).convert("RGBA")
    sw, sh = screen.size
    pad_x, pad_y, bezel = 28, 48, 18
    mw, mh = sw + pad_x * 2 + bezel * 2, sh + pad_y * 2 + bezel * 2 + 36
    bg = Image.new("RGBA", (mw, mh), "#1a1814")
    draw = ImageDraw.Draw(bg)
    draw.rounded_rectangle([bezel, bezel, mw - bezel, mh - bezel - 20], radius=48, fill="#0d0c0a", outline="#3d3830", width=4)
    nw = 120
    draw.rounded_rectangle([(mw - nw) // 2, bezel + 8, (mw + nw) // 2, bezel + 36], radius=14, fill="#0d0c0a")
    mask = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, sw, sh], radius=32, fill=255)
    screen.putalpha(mask)
    bg.paste(screen, (bezel + pad_x, bezel + pad_y), screen)
    draw.ellipse([(mw - 64) // 2, mh - 52, (mw + 64) // 2, mh - 20], fill="#2a2620")
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.convert("RGB").save(out, "PNG", optimize=True)
    return out


def resize_play(path: Path, out: Path) -> Path:
    from PIL import Image

    img = Image.open(path).convert("RGB").resize((1080, 1920), Image.Resampling.LANCZOS)
    img.save(out, "PNG", optimize=True)
    return out


def capture() -> list[Path]:
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
        )
        for name, route, tx, ty, label in SCENES:
            page.goto(f"{BASE}{route}", wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(2800)
            if "lei-seca" in name:
                page.evaluate("window.scrollTo(0, 380)")
                page.wait_for_timeout(500)
            clean_ui(page)
            raw = OUT / f"{name}.png"
            page.screenshot(path=str(raw), full_page=False)
            touched = touch_overlay(raw, tx * 3, ty * 3, label)
            mockup = phone_mockup(touched, OUT / f"{name}-celular-mockup.png")
            screen = resize_play(touched, OUT / f"{name}-1080x1920.png")
            results.extend([mockup, screen])
            print(f"  {mockup.name}", flush=True)
            print(f"  {screen.name}", flush=True)
        browser.close()
    return results


def main() -> int:
    ensure_deps()
    server = start_server()
    try:
        print("==> Uso no celular (2 cenas)", flush=True)
        paths = capture()
    finally:
        server.terminate()
        server.wait(timeout=5)

    DOCS.mkdir(parents=True, exist_ok=True)
    for src in paths:
        (DOCS / src.name).write_bytes(src.read_bytes())
    subprocess.run(["open", str(DOCS)], check=False)
    print(f"\nSalvo em:\n  {OUT}\n  {DOCS}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
