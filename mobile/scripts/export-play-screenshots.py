#!/usr/bin/env python3
"""Capturas do NaIntegra Lex para Google Play (phone, tablet, Chromebook, Android XR)."""
from __future__ import annotations

import argparse
import io
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
GENERATED = MOBILE / "store-assets" / "generated"
DOCS = Path.home() / "Documents" / "NaIntegra-Lex-GooglePlay"
BASE = "http://127.0.0.1:8765/web/lex/index.html?promo=1"

SCENES = [
    ("01-inicio", "#/", None),
    ("02-lei-seca", "#/lei-seca", "scroll:320"),
    ("03-flashcards", "#/flashcards", None),
    ("04-questoes", "#/questoes", "scroll:120"),
    ("05-jurisprudencia", "#/jurisprudencia", "scroll:280"),
    ("06-favoritos", "#/favoritos", None),
    ("07-plano-estudos", "#/plano-estudos", None),
]

SCENE_CAPTIONS = {
    "01-inicio": "Legislação e jurisprudência para concursos",
    "02-lei-seca": "Lei seca · grifos, anotações e narração",
    "03-flashcards": "Flashcards com repetição espaçada",
    "04-questoes": "Questões comentadas por banca",
    "05-jurisprudencia": "Súmulas e temas STF / STJ",
    "06-favoritos": "Seus precedentes favoritos",
    "07-plano-estudos": "Trilha de estudos por carreira",
}

DEVICES: dict[str, dict] = {
    "phone": {
        "label": "Telefone",
        "viewport": {"width": 390, "height": 844},
        "scale": 3,
        "output": (1080, 1920),
        "mobile": True,
    },
    "tablet-7": {
        "label": "Tablet 7\"",
        "viewport": {"width": 800, "height": 1280},
        "scale": 1,
        "output": (1200, 1920),
        "mobile": False,
    },
    "tablet-10": {
        "label": "Tablet 10\"",
        "viewport": {"width": 1000, "height": 1600},
        "scale": 1,
        "output": (1600, 2560),
        "mobile": False,
    },
    "chromebook": {
        "label": "Chromebook",
        "viewport": {"width": 1920, "height": 1080},
        "scale": 1,
        "output": (1920, 1080),
        "mobile": False,
    },
    "android-xr": {
        "label": "Android XR",
        "viewport": {"width": 1920, "height": 1200},
        "scale": 1,
        "output": (1920, 1200),
        "mobile": False,
    },
}


def ensure_playwright() -> None:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "pillow", "-q"], check=True)
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
          document.getElementById('lex-onboarding')?.remove();
          document.getElementById('lex-feedback-banner')?.remove();
          document.body.classList.remove('lex-onboarding-open');
        }"""
    )


def apply_caption(path: Path, caption: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(path).convert("RGBA")
    w, h = img.size
    bar_h = max(72, int(h * 0.09))
    overlay = Image.new("RGBA", (w, bar_h), (26, 24, 20, 220))
    img.paste(overlay, (0, h - bar_h), overlay)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", max(22, int(w * 0.028)))
    except OSError:
        font = ImageFont.load_default()
    tw = draw.textlength(caption, font=font)
    draw.text(((w - tw) / 2, h - bar_h + (bar_h - 28) / 2), caption, fill="#ffffff", font=font)
    img.convert("RGB").save(path, "PNG", optimize=True)


def save_shot(page, out: Path, size: tuple[int, int]) -> None:
    from PIL import Image

    raw = page.screenshot(full_page=False, timeout=30_000)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if img.size != size:
        img = img.resize(size, Image.Resampling.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)


def navigate_scene(page, route: str, action: str | None) -> None:
    page.goto(f"{BASE}{route}", wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(2200)
    if action and action.startswith("scroll:"):
        page.evaluate(f"window.scrollTo(0, {action.split(':')[1]})")
        page.wait_for_timeout(500)


def capture_all(devices: list[str]) -> dict[str, list[Path]]:
    from playwright.sync_api import sync_playwright

    all_paths: dict[str, list[Path]] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for device_id in devices:
            cfg = DEVICES[device_id]
            out_w, out_h = cfg["output"]
            out_dir = GENERATED / device_id
            paths: list[Path] = []

            print(f"\n==> {cfg['label']} ({out_w}×{out_h})", flush=True)
            context = browser.new_context(
                viewport=cfg["viewport"],
                device_scale_factor=cfg.get("scale", 1),
                is_mobile=cfg.get("mobile", False),
                has_touch=cfg.get("mobile", False),
            )
            page = context.new_page()
            page.goto(BASE, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(3000)
            clean_ui(page)

            for name, route, action in SCENES:
                navigate_scene(page, route, action)
                clean_ui(page)
                out = out_dir / f"screenshot-{name}-{out_w}x{out_h}.png"
                save_shot(page, out, (out_w, out_h))
                cap = SCENE_CAPTIONS.get(name)
                if cap:
                    apply_caption(out, cap)
                paths.append(out)
                print(f"  {out.name}", flush=True)

            context.close()
            all_paths[device_id] = paths

        browser.close()
    return all_paths


def copy_to_documents(all_paths: dict[str, list[Path]]) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    for name, src in (
        ("feature-graphic-1024x500.png", GENERATED / "feature-graphic-1024x500.png"),
        ("icon-512-play-store.png", GENERATED / "icon-512-play-store.png"),
    ):
        if src.exists():
            (DOCS / name).write_bytes(src.read_bytes())

    for device_id, paths in all_paths.items():
        dest_dir = DOCS / device_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src in paths:
            (dest_dir / src.name).write_bytes(src.read_bytes())

    subprocess.run(["open", str(DOCS)], check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=[*DEVICES.keys(), "all"], default="all")
    args = parser.parse_args()

    ensure_playwright()
    targets = list(DEVICES.keys()) if args.device == "all" else [args.device]

    server = start_server()
    try:
        all_paths = capture_all(targets)
    finally:
        server.terminate()
        server.wait(timeout=5)

    copy_to_documents(all_paths)
    print(f"\nSalvo em:\n  {GENERATED}\n  {DOCS}", flush=True)
    for device_id, paths in all_paths.items():
        print(f"  {device_id}: {len(paths)} imagens", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
