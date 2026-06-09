"""Renderiza slides de carrossel / capa Reels (1080px) — sempre disponível."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

BRAND = {
    "bg": (13, 13, 15),
    "panel": (22, 22, 26),
    "gold": (201, 168, 76),
    "text": (245, 240, 230),
    "muted": (160, 150, 130),
}

MINIMAL_WHITE = {
    "bg": (255, 255, 255),
    "text": (0, 0, 0),
    "muted": (40, 40, 40),
}


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    candidates = [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def render_slide_minimal_white(
    *,
    text: str,
    footer: str = "@delegadoluizcarlos",
    out_path: Path,
    size: tuple[int, int] = (1080, 1080),
) -> Path:
    """Slide quadrado: fundo branco (#FFF), texto preto — padrão Marketing Digital."""

    from PIL import Image, ImageDraw

    w, h = size
    img = Image.new("RGB", size, MINIMAL_WHITE["bg"])
    draw = ImageDraw.Draw(img)
    margin = 80
    y = margin + 40
    title_font = _font(44, bold=True)
    body_font = _font(32)
    lines = text.strip().split("\n", 1)
    head = lines[0][:120]
    body = lines[1][:500] if len(lines) > 1 else ""
    for line in textwrap.wrap(head, width=24):
        draw.text((margin, y), line, fill=MINIMAL_WHITE["text"], font=title_font)
        y += 52
    if body:
        y += 20
        for line in textwrap.wrap(body, width=30):
            if y > h - margin - 100:
                break
            draw.text((margin, y), line, fill=MINIMAL_WHITE["muted"], font=body_font)
            y += 42
    draw.text((margin, h - margin - 36), footer, fill=MINIMAL_WHITE["muted"], font=_font(22))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path


def render_slide(
    *,
    title: str,
    body: str,
    footer: str = "@delegadoluizcarlos",
    slide_label: str = "",
    size: tuple[int, int] = (1080, 1350),
    out_path: Path,
    style: str = "brand",
) -> Path:
    if style == "minimal_white":
        return render_slide_minimal_white(
            text=f"{title}\n{body}".strip(),
            footer=footer,
            out_path=out_path,
            size=(size[0], size[0]) if size[0] == size[1] else (1080, 1080),
        )

    from PIL import Image, ImageDraw

    w, h = size
    img = Image.new("RGB", size, BRAND["bg"])
    draw = ImageDraw.Draw(img)
    margin = 72
    draw.rounded_rectangle(
        [margin, margin, w - margin, h - margin - 40],
        radius=32,
        fill=BRAND["panel"],
        outline=BRAND["gold"],
        width=3,
    )

    y = margin + 48
    if slide_label:
        draw.text((margin + 40, y), slide_label, fill=BRAND["gold"], font=_font(28))
        y += 52

    title_font = _font(52, bold=True)
    for line in textwrap.wrap(title, width=22):
        draw.text((margin + 40, y), line, fill=BRAND["text"], font=title_font)
        y += 58

    y += 24
    body_font = _font(36)
    for line in textwrap.wrap(body, width=28):
        if y > h - margin - 160:
            break
        draw.text((margin + 40, y), line, fill=BRAND["muted"], font=body_font)
        y += 46

    draw.text((margin + 40, h - margin - 90), footer, fill=BRAND["gold"], font=_font(26))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path


def render_slides_from_package(
    package: dict[str, Any],
    out_dir: Path,
    *,
    formato: str = "carrossel",
    slide_style: str = "brand",
) -> list[dict[str, str]]:
    """Gera PNGs locais; retorna lista {path, label, kind}."""

    assets: list[dict[str, str]] = []
    titulo = str(package.get("titulo") or "NaIntegra")
    gancho = str(package.get("gancho") or package.get("texto_overlay") or "")

    slide_size = (1080, 1080) if slide_style == "minimal_white" else (
        (1080, 1350) if formato == "carrossel" else (1080, 1920)
    )
    cover = out_dir / "00_capa.png"
    render_slide(
        title=titulo[:80],
        body=gancho[:200] or "Indo DIRETO ao ponto",
        slide_label="CAPA",
        out_path=cover,
        size=slide_size,
        style=slide_style,
    )
    assets.append({"path": str(cover), "label": "Capa", "kind": "cover"})

    slides = package.get("slides") or []
    if isinstance(slides, list):
        for i, slide in enumerate(slides, start=1):
            if isinstance(slide, dict):
                st = str(slide.get("titulo") or slide.get("title") or f"Slide {i}")
                sb = str(
                    slide.get("corpo")
                    or slide.get("body")
                    or slide.get("texto")
                    or slide.get("text_content")
                    or ""
                )
            else:
                st = f"Slide {i}"
                sb = str(slide)
            path = out_dir / f"{i:02d}_slide.png"
            render_slide(
                title=st[:100],
                body=sb[:400],
                slide_label=f"{i}/{len(slides)}",
                out_path=path,
                size=slide_size,
                style=slide_style,
            )
            assets.append({"path": str(path), "label": st[:60], "kind": "slide"})

    cta_path = out_dir / "99_cta.png"
    render_slide(
        title="Comente MATERIAL",
        body=str(package.get("cta") or "Receba o material NaIntegra no inbox. Link na bio."),
        slide_label="CTA",
        out_path=cta_path,
        size=slide_size,
        style=slide_style,
    )
    assets.append({"path": str(cta_path), "label": "CTA", "kind": "cta"})
    return assets
