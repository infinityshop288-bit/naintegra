from __future__ import annotations

import html as html_std
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _slug(s: str, max_len: int = 48) -> str:
    nrm = unicodedata.normalize("NFD", s)
    ascii_n = "".join(c for c in nrm if unicodedata.category(c) != "Mn")
    slug = re.sub(r"[^\w\s-]", "", ascii_n.lower())
    slug = re.sub(r"[\s_]+", "-", slug.strip())[:max_len].strip("-")
    return slug or "tema"


def _simple_markdown_to_html(md: str) -> str:
    chunks = []
    for para_raw in md.split("\n\n"):
        para_stripped = para_raw.strip()
        if not para_stripped:
            continue

        if para_stripped.startswith("### "):
            t = html_std.escape(para_stripped[4:].strip())
            chunks.append(f"<h4>{t}</h4>")
            continue

        if para_stripped.startswith("## "):
            chunks.append(f"<h3>{html_std.escape(para_stripped[3:].strip())}</h3>")
            continue

        lines_nl = para_stripped.split("\n")
        lines = [l.strip() for l in lines_nl if l.strip()]
        if lines and all(l.startswith(("- ", "* ")) for l in lines):
            items = "".join(f"<li>{html_std.escape(l[2:].strip())}</li>" for l in lines)
            chunks.append(f"<ul>{items}</ul>")
            continue

        body_parts = []
        for line in lines_nl:
            lst = line.strip()
            if not lst:
                continue
            body_parts.append(html_std.escape(lst))
        body = "<br />\n".join(body_parts)
        chunks.append(f"<p>{body}</p>")
    return "\n".join(chunks)


def build_review_html(settings: Any) -> Path:
    studies_dir = Path(settings.studies_dir)
    out_path = Path(settings.review_html_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    if studies_dir.exists():
        for p in sorted(studies_dir.glob("*.json")):
            try:
                items.append(json.loads(p.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Ignorando %s: %s", p, e)

    nav_parts = []
    body_parts = []
    for idx, doc in enumerate(items, start=1):
        stem_short = str(doc.get("stem_key") or idx)[:20]
        enun = doc.get("enunciado") or ""
        snippet = html_std.escape(enun[:160]) + ("…" if len(enun) > 160 else "")
        disc = html_std.escape(str(doc.get("disciplina") or "—"))
        cid = _slug(enun[:80])
        anchor = f"q-{cid}-{stem_short}"
        anchor = re.sub(r"[^a-zA-Z0-9_-]", "-", anchor)[:96]
        nav_parts.append(f'<li><a href="#{anchor}">{snippet}</a></li>')
        md = doc.get("markdown") or ""
        ai_html = _simple_markdown_to_html(md)

        opts = doc.get("alternativas") or {}
        opts_html = ""
        if isinstance(opts, dict) and opts:
            li = "".join(
                f"<li><strong>{html_std.escape(str(k))}.</strong> {html_std.escape(str(v))}</li>"
                for k, v in sorted(opts.items())
            )
            opts_html = f'<ol class="alts">{li}</ol>'

        body_parts.append(
            f'<article id="{anchor}" class="card">\n'
            f'<header><span class="badge">{disc}</span></header>\n'
            f'<section class="enunciado"><h3>Enunciado</h3><blockquote>{html_std.escape(enun)}</blockquote>'
            f"{opts_html}</section>\n"
            f'<section class="perspectiva"><h3>Perspectiva da IA para o tema</h3>{ai_html}</section>\n'
            f"</article>\n"
        )

    nav = (
        "<ul>" + "".join(nav_parts) + "</ul>"
        if nav_parts
        else "<p>Nenhum estudo encontrado na pasta configurada.</p>"
    )

    inbox_note = html_std.escape(str(studies_dir))

    page = f"""<!DOCTYPE html>
<html lang="pt-BR">
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Revisão — erros consolidados × perspectiva IA</title>
<style>
:root {{
  font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  line-height: 1.48;
  color: #171412;
  background: #faf8f5;
}}
body {{ margin: 0; display: flex; max-width: 1200px; min-height: 100vh; margin-inline: auto; }}
nav.sidebar {{
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid #e3ddd4;
  padding: 1.2rem;
  background: #f3efe8;
  position: sticky;
  top: 0;
  align-self: flex-start;
  max-height: 100vh;
  overflow: auto;
  font-size: 0.9rem;
}}
main {{ flex: 1; padding: 1.5rem 1.8rem; }}
article.card {{
  margin-bottom: 2.8rem;
  padding-bottom: 2rem;
  border-bottom: 1px dashed #dcd5c9;
}}
.badge {{
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: .06em;
  background: #2c3e50;
  color: #eef3f8;
  padding: .28rem .55rem;
  border-radius: 4px;
}}
blockquote {{
  margin: .6rem 0 1rem;
  padding-left: 1rem;
  border-left: 4px solid #b8956a;
}}
ol.alts {{ padding-left: 1.25rem; }}
section.perspectiva h4 {{
  margin: 1.2rem 0 .4rem;
  font-size: 1.05rem;
  color: #3d3429;
}}
h1 {{ font-size: 1.45rem; font-weight: 600; }}
h3 {{ font-size: 1.08rem; margin-top: 0; }}
a {{ color: #1a5276; text-decoration-thickness: 1px; }}
nav ul {{ list-style: none; padding-left: 0; margin: .5rem 0; }}
nav li {{ margin-bottom: .45rem; }}
@media (max-width: 820px) {{
  body {{ flex-direction: column; }}
  nav.sidebar {{
    width: auto;
    position: relative;
    max-height: none;
    border-right: none;
    border-bottom: 1px solid #e3ddd4;
  }}
}}
</style>
<body>
<nav class="sidebar">
  <h1>Índice</h1>
  {nav}
</nav>
<main>
  <h1>Revisão objetiva para prova</h1>
  <p>Cartões montados automaticamente dos JSON em <code>{inbox_note}</code>.</p>
  {"".join(body_parts)}
</main>
</body>
</html>"""

    out_path.write_text(page, encoding="utf-8")
    logger.info("HTML escrito %s (%s cartões)", out_path, len(body_parts))
    return out_path
