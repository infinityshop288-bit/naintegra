"""Skills em formato SKILL.md (frontmatter + instruções)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = ROOT / "data" / "lex_skills"
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(name: str) -> str:
    raw = (name or "").strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return raw[:80]


def parse_skill_md(text: str) -> dict[str, str]:
    body = text.lstrip("\ufeff")
    meta: dict[str, str] = {}
    rest = body
    if body.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip().strip('"').strip("'")
            rest = parts[2].lstrip("\n")
    return {
        "name": meta.get("name") or "",
        "description": meta.get("description") or "",
        "body": rest.strip(),
    }


def skill_to_md(name: str, description: str, body: str) -> str:
    return (
        f"---\nname: {name}\ndescription: {description.strip()}\n---\n\n{body.strip()}\n"
    )


def list_skills() -> list[dict[str, Any]]:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    out: list[dict[str, Any]] = []
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        parsed = parse_skill_md(path.read_text(encoding="utf-8"))
        slug = path.parent.name
        out.append(
            {
                "slug": slug,
                "name": parsed["name"] or slug,
                "description": parsed["description"],
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            }
        )
    return out


def read_skill(slug: str) -> dict[str, Any] | None:
    clean = slugify(slug)
    path = SKILLS_DIR / clean / "SKILL.md"
    if not path.is_file():
        return None
    parsed = parse_skill_md(path.read_text(encoding="utf-8"))
    return {
        "slug": clean,
        "name": parsed["name"] or clean,
        "description": parsed["description"],
        "body": parsed["body"],
    }


def save_skill(name: str, description: str, body: str) -> dict[str, Any]:
    slug = slugify(name)
    if not slug or not _SLUG_RE.match(slug):
        raise ValueError("nome da skill inválido")
    if len((body or "").strip()) < 20:
        raise ValueError("instruções da skill muito curtas")
    folder = SKILLS_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "SKILL.md"
    path.write_text(skill_to_md(slug, description or name, body), encoding="utf-8")
    saved = read_skill(slug)
    assert saved
    return saved


def seed_builtin_skills() -> None:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    builtins = {
        "peca-inicial": (
            "Elabora petição inicial cível ou penal com fatos, direito e pedidos.",
            "# Peça inicial\n\nEstruture: endereçamento, qualificação, fatos, direito (cite só o acervo), pedidos e valor da causa se couber.\nNão invente artigo, súmula ou processo. Se faltar base, peça pesquisa no acervo.",
        ),
        "parecer-juridico": (
            "Elabora parecer objetivo com tese, fundamentos e conclusão.",
            "# Parecer jurídico\n\nUse: relatório breve, questão jurídica, fundamentação com lei/júris do acervo, conclusão e recomendações.\nNão invente precedentes.",
        ),
        "recurso": (
            "Elabora razões de recurso (apelação, agravo, RE/REsp) a partir do acervo.",
            "# Recurso\n\nIndique cabimento, tempestividade, preliminares, mérito e pedidos. Fundamente só com o material localizado.",
        ),
        "resumo-norma": (
            "Resume lei ou dispositivo para estudo de concurso.",
            "# Resumo de norma\n\nTraga ementa de estudo, estrutura da lei, artigos-chave (transcrição só se estiver no acervo) e pegadinhas de prova.",
        ),
        "tese-jurisprudencial": (
            "Organiza tese de súmula ou tema repetitivo/repercussão geral.",
            "# Tese jurisprudencial\n\nEnunciado oficial, alcance, distinção e aplicação em prova. Não invente número de súmula ou tema.",
        ),
        "discursiva": (
            "Elabora resposta dissertativa de concurso (juiz, MP, DP, procuradoria).",
            "# Discursiva\n\nIntrodução, desenvolvimento com lei e jurisprudência do acervo, conclusão. Linguagem de banca.",
        ),
    }
    for slug, (desc, body) in builtins.items():
        path = SKILLS_DIR / slug / "SKILL.md"
        if path.is_file():
            continue
        save_skill(slug, desc, body)
