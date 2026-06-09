"""Biblioteca Marketing Digital — repo infinityshop288-bit/marketingdigital."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
BUNDLED = REPO / "data" / "delegado" / "marketing_digital" / "library.json"
DEFAULT_MARKETING_REPO = REPO / "data" / "delegado" / "marketing_digital" / "repo"
REPO_URL = "https://github.com/infinityshop288-bit/marketingdigital.git"

PRIORITY_FILES = (
    "supabase/functions/ai-generate-content/index.ts",
    "supabase/functions/auto-generate-content/index.ts",
    "supabase/functions/ai-generate-images/index.ts",
    "supabase/functions/ai-social-content/index.ts",
    "supabase/functions/ai-trends/index.ts",
    "src/lib/automationPlaybooks.ts",
    "src/pages/CriarConteudo.tsx",
    "src/pages/DelegadoHub.tsx",
)

SUPPORTED_EXT = {".md", ".txt", ".json", ".ts", ".tsx"}


def marketing_repo_path() -> Path | None:
    raw = os.environ.get("DELEGADO_MARKETING_REPO_PATH", "").strip()
    if raw:
        p = Path(raw).expanduser()
        if p.is_dir():
            return p.resolve()
    if DEFAULT_MARKETING_REPO.is_dir():
        return DEFAULT_MARKETING_REPO.resolve()
    for name in ("marketingdigital", "Marketing-Digital", "marketing-digital"):
        p = REPO.parent / name
        if p.is_dir():
            return p.resolve()
    return None


def load_bundled_library() -> dict[str, Any]:
    if BUNDLED.is_file():
        return json.loads(BUNDLED.read_text(encoding="utf-8"))
    return {"brand": {}, "hooks": [], "cta_blocks": []}


def _extract_ts_prompt(path: Path, var_name: str) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    # const systemPrompt = `...`;
    patterns = [
        rf"const\s+{var_name}\s*=\s*`([^`]+)`",
        rf"const\s+{var_name}\s*=\s*\"([^\"]+)\"",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


def _extract_category_descriptions(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="ignore")
    block = re.search(r"categoryDescriptions:\s*Record<string,\s*string>\s*=\s*\{([^}]+)\}", text, re.DOTALL)
    if not block:
        return {}
    out: dict[str, str] = {}
    for m in re.finditer(r"(\w+):\s*\"([^\"]+)\"", block.group(1)):
        out[m.group(1)] = m.group(2)
    return out


def _extract_image_slide_template(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"text:\s*`(Create a clean Instagram carousel slide[^`]+)`", text, re.DOTALL)
    return m.group(1).strip() if m else None


def load_marketing_digital_assets() -> dict[str, Any]:
    """Prompts e templates extraídos do repo marketingdigital."""

    root = marketing_repo_path()
    assets: dict[str, Any] = {
        "repo_url": REPO_URL,
        "repo_path": str(root) if root else None,
        "content_system_prompt": None,
        "auto_content_system_prompt": None,
        "image_slide_template": None,
        "categories": {},
        "playbooks_summary": [],
    }
    if not root:
        return assets

    gen_content = root / "supabase/functions/ai-generate-content/index.ts"
    auto_gen = root / "supabase/functions/auto-generate-content/index.ts"
    gen_images = root / "supabase/functions/ai-generate-images/index.ts"
    playbooks = root / "src/lib/automationPlaybooks.ts"

    assets["content_system_prompt"] = _extract_ts_prompt(gen_content, "systemPrompt")
    assets["auto_content_system_prompt"] = _extract_ts_prompt(auto_gen, "systemPrompt")
    assets["image_slide_template"] = _extract_image_slide_template(gen_images)
    assets["categories"] = _extract_category_descriptions(gen_content)

    if playbooks.is_file():
        txt = playbooks.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'name:\s*"([^"]+)"[^}]*tagline:\s*"([^"]+)"', txt):
            assets["playbooks_summary"].append({"name": m.group(1), "tagline": m.group(2)})

    return assets


def get_content_system_prompt(*, academic: bool = False) -> str:
    """Prompt do app Marketing Digital (JSON slides/caption) — use em integrações MD puras."""

    md = load_marketing_digital_assets()
    prompt = md.get("auto_content_system_prompt") if academic else md.get("content_system_prompt")
    if prompt:
        return prompt
    from naintegra_meta.zamboni_style import SYSTEM_PROMPT_ZAMBONI

    return SYSTEM_PROMPT_ZAMBONI


def get_package_system_prompt() -> str:
    """Pacote NaIntegra: schema Zamboni + trecho do estilo Marketing Digital."""

    from naintegra_meta.zamboni_style import SYSTEM_PROMPT_PACKAGE

    md = load_marketing_digital_assets()
    excerpt = (md.get("content_system_prompt") or "")[:1500]
    if excerpt:
        return (
            SYSTEM_PROMPT_PACKAGE
            + "\n\n--- Referência editorial (Marketing Digital / @profalexandrezamboni) ---\n"
            + excerpt
            + "\n\nMantenha o objeto JSON do pacote NaIntegra (titulo, gancho, legenda, slides com titulo/corpo)."
        )
    return SYSTEM_PROMPT_PACKAGE


def get_image_prompt_for_slide(slide_text: str) -> str:
    md = load_marketing_digital_assets()
    tpl = md.get("image_slide_template")
    if tpl:
        return tpl.replace("${slideText}", slide_text).replace("${slideText}", slide_text)
    lib = load_bundled_library()
    base = lib.get("image_style_prompt") or "Professional legal Instagram slide"
    return f"{base}\n\nSlide text:\n{slide_text}"


def marketing_image_model() -> str:
    return (
        os.environ.get("DELEGADO_GEMINI_IMAGE_MODEL", "").strip()
        or "gemini-3.1-flash-image-preview"
    )


def _walk_snippets(root: Path, limit: int = 15) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for rel in PRIORITY_FILES:
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")[:2000]
        out.append({"path": rel, "excerpt": text})
        if len(out) >= limit:
            break
    return out


def build_marketing_context(max_chars: int = 8000) -> str:
    lib = load_bundled_library()
    md = load_marketing_digital_assets()
    parts: list[str] = [
        f"## Marketing Digital ({REPO_URL})",
        f"Repo local: {md.get('repo_path') or 'não clonado'}",
        "## Marca",
        json.dumps(lib.get("brand") or {}, ensure_ascii=False),
        "## Categorias de conteúdo (app Marketing Digital)",
        json.dumps(md.get("categories") or {}, ensure_ascii=False, indent=0),
        "## Playbooks de automação",
        json.dumps(md.get("playbooks_summary") or [], ensure_ascii=False),
        "## Ganchos",
        "\n".join(f"- {h}" for h in (lib.get("hooks") or [])[:10]),
        "## CTAs",
        "\n".join(f"- {c}" for c in (lib.get("cta_blocks") or [])[:6]),
    ]
    prompt_excerpt = (md.get("content_system_prompt") or "")[:1500]
    if prompt_excerpt:
        parts.append("## Prompt oficial ai-generate-content (trecho)\n" + prompt_excerpt)

    root = marketing_repo_path()
    if root:
        for snip in _walk_snippets(root, limit=8):
            parts.append(f"### {snip['path']}\n{snip['excerpt'][:800]}")

    return "\n\n".join(parts)[:max_chars]


def library_status() -> dict[str, Any]:
    repo = marketing_repo_path()
    md = load_marketing_digital_assets()
    return {
        "repo_url": REPO_URL,
        "bundled_library": BUNDLED.is_file(),
        "repo_path": str(repo) if repo else None,
        "repo_cloned": bool(repo and (repo / ".git").exists()),
        "categories": md.get("categories") or {},
        "playbooks": md.get("playbooks_summary") or [],
        "has_content_prompt": bool(md.get("content_system_prompt")),
        "has_image_template": bool(md.get("image_slide_template")),
        "gemini_image_model": marketing_image_model(),
        "priority_files_found": sum(
            1 for rel in PRIORITY_FILES if repo and (repo / rel).is_file()
        ),
    }
