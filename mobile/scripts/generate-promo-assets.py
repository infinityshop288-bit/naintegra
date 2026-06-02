#!/usr/bin/env python3
"""Gera imagens de uso (mockup + toque) e vídeo promocional do NaIntegra Lex."""
from __future__ import annotations

import math
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
OUT = MOBILE / "store-assets" / "promo"
RAW = OUT / "raw"
MOCKUP = OUT / "usage-mockups"
VIDEO_OUT = OUT / "naintegra-lex-promo-1080x1920.mp4"
DOWNLOADS = Path.home() / "Downloads" / "NaIntegra-Lex-Promo"
BASE_URL = "http://127.0.0.1:8765/web/lex/index.html?promo=1"
VIEWPORT = {"width": 390, "height": 844}


def ensure_deps() -> None:
    for pkg in ("pillow", "playwright", "imageio", "numpy"):
        try:
            __import__(pkg)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "imageio[ffmpeg]", "-q"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def start_server() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "preview" / "serve_preview.py"), "--port", "8765", "--open", "none"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.2)
    return proc


def touch_overlay(path: Path, x: int, y: int, label: str | None = None) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    r = 28
    draw.ellipse([x - r, y - r, x + r, y + r], fill=(154, 110, 0, 90), outline=(255, 255, 255, 200), width=3)
    draw.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(255, 255, 255, 180))
    if label:
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


def phone_mockup(screenshot: Path, name: str) -> Path:
    from PIL import Image, ImageDraw

    screen = Image.open(screenshot).convert("RGBA")
    sw, sh = screen.size
    pad_x, pad_y, bezel = 28, 48, 18
    mw, mh = sw + pad_x * 2 + bezel * 2, sh + pad_y * 2 + bezel * 2 + 36
    canvas = Image.new("RGBA", (mw, mh), (0, 0, 0, 0))
    bg = Image.new("RGBA", (mw, mh), "#1a1814")
    draw = ImageDraw.Draw(bg)
    inner = [bezel, bezel, mw - bezel, mh - bezel - 20]
    draw.rounded_rectangle(inner, radius=48, fill="#0d0c0a", outline="#3d3830", width=4)
    notch_w, notch_h = 120, 28
    draw.rounded_rectangle(
        [(mw - notch_w) // 2, bezel + 8, (mw + notch_w) // 2, bezel + 8 + notch_h],
        radius=14,
        fill="#0d0c0a",
    )
    mask = Image.new("L", (sw, sh), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, sw, sh], radius=32, fill=255)
    screen.putalpha(mask)
    px = bezel + pad_x
    py = bezel + pad_y
    bg.paste(screen, (px, py), screen)
    draw.ellipse([(mw - 64) // 2, mh - 52, (mw + 64) // 2, mh - 20], fill="#2a2620")
    out = MOCKUP / f"{name}-mockup.png"
    bg.convert("RGB").save(out, "PNG", optimize=True)
    return out


def capture_usage() -> list[Path]:
    from playwright.sync_api import sync_playwright

    RAW.mkdir(parents=True, exist_ok=True)
    shots: list[tuple[str, Path, int, int, str | None]] = []

    scenarios = [
        ("01-dashboard", "#/"),
        ("02-lei-seca", "#/lei-seca"),
        ("03-flashcards", "#/flashcards"),
        ("04-questoes", "#/questoes"),
        ("05-jurisprudencia", "#/jurisprudencia"),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport=VIEWPORT,
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
        )
        page.goto(BASE_URL, wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(3500)

        for name, route in scenarios:
            page.goto(f"{BASE_URL}{route}", wait_until="networkidle", timeout=120_000)
            page.wait_for_timeout(2500)
            if "lei-seca" in name:
                page.evaluate("window.scrollTo(0, 420)")
                page.wait_for_timeout(800)
            if "flashcards" in name:
                btn = page.locator(".deck-card, .section-list-scope a, .btn").first
                if btn.count():
                    try:
                        btn.click(timeout=5000)
                        page.wait_for_timeout(1500)
                    except Exception:
                        pass
            if "questoes" in name:
                page.evaluate("window.scrollTo(0, 300)")
                page.wait_for_timeout(600)
            path = RAW / f"usage-{name}.png"
            page.screenshot(path=str(path), full_page=False)
            touch_x, touch_y = 195, 520
            label = {
                "01-dashboard": "Início",
                "02-lei-seca": "Lei seca",
                "03-flashcards": "Flashcards",
                "04-questoes": "Questões",
                "05-jurisprudencia": "Jurisprudência",
                "06-leitor": "Lendo artigo",
            }.get(name)
            shots.append((name, path, touch_x, touch_y, label))
            print(f"  captura: {path.name}")

        # Leitor de artigo
        page.goto(f"{BASE_URL}#/lei-seca", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(2000)
        link = page.locator(".section-list-scope a, .doc-row a, a[href*='lei-seca/']").first
        if link.count():
            try:
                link.click(timeout=8000)
                page.wait_for_timeout(3500)
                page.evaluate("window.scrollTo(0, 280)")
                page.wait_for_timeout(800)
                path = RAW / "usage-06-leitor.png"
                page.screenshot(path=str(path), full_page=False)
                shots.append(("06-leitor", path, 210, 640, "Lendo artigo"))
                print(f"  captura: {path.name}")
            except Exception as exc:
                print(f"  [AVISO] leitor: {exc}")

        browser.close()

    mockups: list[Path] = []
    MOCKUP.mkdir(parents=True, exist_ok=True)
    for name, raw, tx, ty, label in shots:
        touched = touch_overlay(raw, tx * 3, ty * 3, label)
        mockups.append(phone_mockup(touched, f"usage-{name}"))
        print(f"  mockup: {mockups[-1].name}")
    return mockups


def title_card() -> Path:
    from PIL import Image, ImageDraw, ImageFont

    OUT.mkdir(parents=True, exist_ok=True)
    w, h = 1080, 1920
    img = Image.new("RGB", (w, h), "#faf8f4")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w, 12], fill="#9a6e00")
    draw.rectangle([0, h - 12, w, h], fill="#9a6e00")
    icon = ROOT / "web" / "lex" / "icons" / "icon-512.png"
    if icon.exists():
        logo = Image.open(icon).convert("RGBA").resize((240, 240), Image.Resampling.LANCZOS)
        img.paste(logo, ((w - 240) // 2, 520), logo)
    try:
        t1 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 72)
        t2 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 36)
        t3 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 40)
    except OSError:
        t1 = t2 = t3 = ImageFont.load_default()
    draw.text((w // 2, 820), "NaIntegra Lex", fill="#1a1a1a", font=t1, anchor="mm")
    draw.text(
        (w // 2, 920),
        "Lei seca · Jurisprudência · Flashcards · Questões",
        fill="#5a5348",
        font=t2,
        anchor="mm",
    )
    draw.text((w // 2, 990), "Concursos públicos", fill="#9a6e00", font=t3, anchor="mm")
    draw.text(
        (w // 2, 1060),
        "Atualizado semanalmente · ideal no transporte",
        fill="#5a5348",
        font=t2,
        anchor="mm",
    )
    out = OUT / "slide-00-intro.png"
    img.save(out, "PNG", optimize=True)
    return out


def cta_card() -> Path:
    from PIL import Image, ImageDraw, ImageFont

    w, h = 1080, 1920
    img = Image.new("RGB", (w, h), "#1a1814")
    draw = ImageDraw.Draw(img)
    try:
        t1 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 64)
        t2 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 34)
    except OSError:
        t1 = t2 = ImageFont.load_default()
    draw.text((w // 2, 780), "Estude onde estiver", fill="#ffffff", font=t1, anchor="mm")
    draw.text((w // 2, 880), "Baixe o NaIntegra Lex", fill="#9a6e00", font=t1, anchor="mm")
    draw.text(
        (w // 2, 980),
        "www.naintegracursos.com.br/lex",
        fill="#cccccc",
        font=t2,
        anchor="mm",
    )
    out = OUT / "slide-99-cta.png"
    img.save(out, "PNG", optimize=True)
    return out


def resize_cover(path: Path, w: int = 1080, h: int = 1920) -> Path:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    img = img.crop((left, top, left + w, top + h))
    out = OUT / f"slide-{path.stem}-1080.png"
    img.save(out, "PNG", optimize=True)
    return out


def build_video(slides: list[Path], seconds_per: float = 3.0, fps: int = 30) -> Path:
    import imageio.v2 as imageio
    import numpy as np
    from PIL import Image

    frames: list[np.ndarray] = []
    frame_count = int(seconds_per * fps)

    def add_slide(path: Path, zoom_start: float = 1.0, zoom_end: float = 1.06) -> None:
        base = Image.open(path).convert("RGB").resize((1080, 1920), Image.Resampling.LANCZOS)
        for i in range(frame_count):
            t = i / max(frame_count - 1, 1)
            zoom = zoom_start + (zoom_end - zoom_start) * t
            zw, zh = int(1080 / zoom), int(1920 / zoom)
            x0 = (1080 - zw) // 2
            y0 = (1920 - zh) // 2
            crop = base.crop((x0, y0, x0 + zw, y0 + zh)).resize((1080, 1920), Image.Resampling.LANCZOS)
            frames.append(np.asarray(crop))

    for slide in slides:
        add_slide(slide)

    OUT.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(VIDEO_OUT),
        fps=fps,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=1,
    )
    try:
        for frame in frames:
            writer.append_data(frame)
    finally:
        writer.close()
    return VIDEO_OUT


def copy_to_downloads(paths: list[Path]) -> None:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for p in paths:
        if p.exists():
            dest = DOWNLOADS / p.name
            dest.write_bytes(p.read_bytes())
    subprocess.run(["open", str(DOWNLOADS)], check=False)


def main() -> int:
    ensure_deps()
    OUT.mkdir(parents=True, exist_ok=True)
    server = start_server()
    try:
        print("==> Capturas de uso (app real + indicador de toque + mockup)")
        mockups = capture_usage()
        print("\n==> Slides do vídeo")
        intro = title_card()
        cta = cta_card()
        slides = [intro]
        for m in mockups[:5]:
            slides.append(resize_cover(m))
        slides.append(resize_cover(cta))
        print("\n==> Vídeo promocional (1080×1920, ~24s)")
        video = build_video(slides, seconds_per=3.0)
        print(f"  {video}")
    finally:
        server.terminate()
        server.wait(timeout=5)

    bundle = [VIDEO_OUT, intro, cta, *mockups]
    copy_to_downloads(bundle)
    print(f"\nPronto em:\n  {OUT}\n  {DOWNLOADS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
