"""Metas de scraping: bancas e cargos alvo (concursos jurídicos)."""

from __future__ import annotations

from urllib.parse import quote_plus

# Bancas prioritárias (canônico para meta.organized / taxonomy).
EXAM_BOARDS: tuple[str, ...] = ("FGV", "FCC", "CEBRASPE", "VUNESP")

# Cargos-alvo (texto padronizado para busca e meta).
EXAM_CARGOS: tuple[str, ...] = (
    "Promotor de Justiça",
    "Juiz de Direito",
    "Procurador da República",
    "Juiz Federal",
    "Procurador do Estado",
    "Procurador da Fazenda Nacional",
    "Procurador do BACEN",
    "Procurador Federal",
    "Advogado da Câmara dos Deputados",
    "Consultor Legislativo do Senado Federal",
    "Advogado da União",
)

# Páginas oficiais (pouco JSON direto; uso como fallback / navegação manual).
OFFICIAL_BANK_HOME: dict[str, str] = {
    "FGV": "https://conhecimento.fgv.br/",
    "FCC": "https://www.fcconcursos.com.br/",
    "CEBRASPE": "https://www.cebraspe.org.br/",
    "VUNESP": "https://www.vunesp.com.br/",
}


def slug_cargo(cargo: str) -> str:
    repl = str.maketrans(
        {
            "ã": "a",
            "â": "a",
            "á": "a",
            "à": "a",
            "ç": "c",
            "é": "e",
            "ê": "e",
            "í": "i",
            "ó": "o",
            "ô": "o",
            "õ": "o",
            "ú": "u",
        }
    )
    s = cargo.lower().translate(repl)
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_"):
            out.append("_")
    slug = "".join(out).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:120] or "cargo"


def slug_board(board: str) -> str:
    return board.strip().upper().replace(" ", "_")


def qconcurso_search_url(board: str, cargo: str) -> str:
    """Busca heurística (calibre com ``playwright-observe`` se o site mudar)."""

    termo = quote_plus(f"{board} {cargo}")
    return f"https://www.qconcursos.com/questoes-de-concursos?termo={termo}"


def techconcursos_search_url(board: str, cargo: str) -> str:
    """Techconcursos — padrão heurístico; ajuste query conforme o site."""

    termo = quote_plus(f"{board} {cargo}")
    return f"https://www.tecconcursos.com.br/questoes/busca?termo={termo}"
