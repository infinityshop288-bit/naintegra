"""Normalização de português jurídico (norma culta) — espelho de web/lex/js/pt-norma.js."""

from __future__ import annotations

import re
from typing import Literal

VERSION = 2

Domain = Literal["legis", "juris", "all"]

MOJIBAKE = [
    ("Ã¡", "á"),
    ("Ã©", "é"),
    ("Ã­", "í"),
    ("Ã³", "ó"),
    ("Ãº", "ú"),
    ("Ã¢", "â"),
    ("Ãª", "ê"),
    ("Ã´", "ô"),
    ("Ã£", "ã"),
    ("Ãµ", "õ"),
    ("Ã§", "ç"),
    ("Ã‰", "É"),
    ("Ãš", "Ú"),
    ("Ãƒ", "Ã"),
    ("Ã•", "Õ"),
    ("Âº", "º"),
    ("Â§", "§"),
    ("ï¿½", ""),
    ("\ufffd", ""),
]

ACCENT_WORDS: list[tuple[str, str]] = [
    ("nao", "não"),
    ("sera", "será"),
    ("serao", "serão"),
    ("sao", "são"),
    ("estara", "estará"),
    ("estarao", "estarão"),
    ("podera", "poderá"),
    ("poderao", "poderão"),
    ("devera", "deverá"),
    ("deverao", "deverão"),
    ("houvera", "houverá"),
    ("tambem", "também"),
    ("porem", "porém"),
    ("alem", "além"),
    ("apos", "após"),
    ("ate", "até"),
    ("ja", "já"),
    ("la", "lá"),
    ("so", "só"),
    ("numero", "número"),
    ("numeros", "números"),
    ("publico", "público"),
    ("publica", "pública"),
    ("publicos", "públicos"),
    ("publicas", "públicas"),
    ("unico", "único"),
    ("unica", "única"),
    ("ultimo", "último"),
    ("ultima", "última"),
    ("constituicao", "constituição"),
    ("organica", "orgânica"),
    ("jurisdicao", "jurisdição"),
    ("competencia", "competência"),
    ("violacao", "violação"),
    ("decisao", "decisão"),
    ("condenacao", "condenação"),
    ("ilicitos", "ilícitos"),
    ("ilicita", "ilícita"),
    ("ilicito", "ilícito"),
    ("administracao", "administração"),
    ("obrigacao", "obrigação"),
    ("obrigacoes", "obrigações"),
    ("disposicao", "disposição"),
    ("disposicoes", "disposições"),
    ("revogacao", "revogação"),
    ("alteracao", "alteração"),
    ("redacao", "redação"),
    ("vigencia", "vigência"),
    ("eficacia", "eficácia"),
    ("licitacao", "licitação"),
    ("contratacao", "contratação"),
    ("sancao", "sanção"),
    ("sancoes", "sanções"),
    ("extraordinario", "extraordinário"),
    ("ordinario", "ordinário"),
    ("publicacao", "publicação"),
    ("sumula", "súmula"),
    ("sumulas", "súmulas"),
    ("observancia", "observância"),
    ("obrigatoria", "obrigatória"),
    ("obrigatorio", "obrigatório"),
    ("repercussao", "repercussão"),
    ("paragrafo", "parágrafo"),
    ("paragrafos", "parágrafos"),
    ("alinea", "alínea"),
    ("alineas", "alíneas"),
    ("codigo", "código"),
    ("codigos", "códigos"),
    ("provisoria", "provisória"),
    ("convenio", "convênio"),
    ("plenario", "plenário"),
    ("plenaria", "plenária"),
    ("tributaria", "tributária"),
    ("tributario", "tributário"),
    ("previdenciario", "previdenciário"),
    ("previdenciaria", "previdenciária"),
    ("intervencao", "intervenção"),
    ("sindicancia", "sindicância"),
    ("anulatoria", "anulatória"),
    ("convalidacao", "convalidação"),
    ("ratificacao", "ratificação"),
    ("homologacao", "homologação"),
    ("adjudicacao", "adjudicação"),
    ("habilitacao", "habilitação"),
    ("qualificacao", "qualificação"),
    ("impugnacao", "impugnação"),
    ("especie", "espécie"),
    ("especies", "espécies"),
    ("beneficio", "benefício"),
    ("beneficios", "benefícios"),
    ("previdencia", "previdência"),
    ("seguranca", "segurança"),
    ("atribuicao", "atribuição"),
    ("atribuicoes", "atribuições"),
    ("responsabilizacao", "responsabilização"),
    ("responsabilizacoes", "responsabilizações"),
    ("indenizacao", "indenização"),
    ("indenizacoes", "indenizações"),
    ("reparacao", "reparação"),
    ("reparacoes", "reparações"),
    ("indenizatorio", "indenizatório"),
    ("indenizatoria", "indenizatória"),
]

GLUED_LEGAL = [
    "público",
    "pública",
    "públicos",
    "públicas",
    "privado",
    "privada",
    "dolosamente",
    "culposamente",
    "administrativa",
    "administrativo",
    "administrativos",
    "constitucionais",
    "jurídica",
    "jurídico",
    "dolosa",
    "doloso",
    "efetivamente",
    "comprovadamente",
    "obrigatoriamente",
    "expressamente",
    "especificamente",
    "respectivamente",
    "independentemente",
    "cumulativamente",
    "subsidiariamente",
    "alternativamente",
]

GLUED_PREPS = [
    "nos",
    "nas",
    "num",
    "numa",
    "pelo",
    "pela",
    "pelos",
    "pelas",
    "que",
    "por",
    "como",
    "para",
    "sem",
    "sobre",
    "entre",
    "contra",
    "mediante",
    "conforme",
    "durante",
]

_SYLLABLE_NO_MERGE = frozenset(
    {
        "de",
        "da",
        "do",
        "dos",
        "das",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "ao",
        "aos",
        "ou",
        "se",
        "um",
        "uma",
        "e",
        "a",
        "o",
        "as",
        "os",
        "que",
        "por",
        "para",
        "com",
        "art",
        "arts",
        "lei",
        "cf",
    }
)


def _match_case(source: str, target: str) -> str:
    if source.isupper():
        return target.upper()
    if source and source[0].isupper():
        return target[:1].upper() + target[1:]
    return target


def format_lei_number(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    digits = digits.lstrip("0") or "0"
    if len(digits) <= 3:
        return digits
    return f"{digits[:-3]}.{digits[-3:]}"


def normalize_lei_references(text: str) -> str:
    """Alinha citações de lei ao padrão Lei 8.112/1990 (espelho de legis-meta.js)."""
    if not text:
        return text
    t = text

    def _lc(m: re.Match[str]) -> str:
        return f"Lei Complementar {format_lei_number(m.group(1).replace('.', ''))}/{m.group(2)}"

    def _lei(m: re.Match[str]) -> str:
        return f"Lei {format_lei_number(m.group(1).replace('.', ''))}/{m.group(2)}"

    t = re.sub(
        r"Lei\s+Complementar\s+(?:n[º°.]?\s*)?([\d.]+)\s*,?\s*de\s+(?:\d+\s+de\s+\w+\s+de\s+)?(\d{4})",
        _lc,
        t,
        flags=re.I,
    )
    t = re.sub(
        r"Lei\s+(?:n[º°.]?\s*)?([\d.]+)\s*,?\s*de\s+\d+\s+de\s+\w+(?:\s+de\s+)?(\d{4})",
        _lei,
        t,
        flags=re.I,
    )
    t = re.sub(
        r"Lei\s+(?:n[º°.]?\s*)?([\d.]+)\s*,?\s*de\s+(\d{4})",
        _lei,
        t,
        flags=re.I,
    )
    t = re.sub(r"Decreto-Lei\s+n[º°.]?\s*", "Decreto-Lei ", t, flags=re.I)
    t = re.sub(r"Decreto\s+n[º°.]?\s*", "Decreto ", t, flags=re.I)
    return t


def fix_mojibake(text: str) -> str:
    if not text or not re.search(r"[ÃÂï¿½\ufffd]", text):
        return text
    t = text
    for bad, good in MOJIBAKE:
        t = t.replace(bad, good)
    return t


def fix_word_accents(text: str) -> str:
    t = text
    for wrong, right in ACCENT_WORDS:
        if wrong == right:
            continue
        t = re.sub(
            rf"\b{re.escape(wrong)}\b",
            lambda m, r=right: _match_case(m.group(0), r),
            t,
            flags=re.I,
        )
    return t


def fix_typography(text: str) -> str:
    t = text
    t = re.sub(r"\s+([,;:.!?])", r"\1", t)
    t = re.sub(r"([,;:])(?=[A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç])", r"\1 ", t)
    t = re.sub(r"\.(?=[A-Za-zÁÉÍÓÚÂÊÔÃÕÇ])", ". ", t)
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"\s+\)", ")", t)
    t = re.sub(r"\.{2,}", ".", t)
    t = re.sub(r",{2,}", ",", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\s+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


def fix_legal_citations(text: str) -> str:
    t = text
    t = re.sub(r"\bSumula\b", "Súmula", t)
    t = re.sub(r"\bsumula\b", "súmula", t)
    t = re.sub(r"\bSUMULA\b", "SÚMULA", t)
    t = re.sub(r"\bS[úu]mula\s+Vinculante\b", "Súmula Vinculante", t, flags=re.I)
    t = re.sub(r"\bn\.\s*º\b", "nº", t, flags=re.I)
    t = re.sub(r"\bn\.\s*°", "nº", t, flags=re.I)
    t = re.sub(r"\bN\.\s*º\b", "Nº", t)
    t = re.sub(r"\b§\s*(\d+)\s*°", r"§ \1º", t, flags=re.I)
    t = re.sub(r"\b§\s*(\d+)\s+o\b", r"§ \1º", t, flags=re.I)
    t = re.sub(r"\bArt\.\s*(\d+)\s*°", r"Art. \1º", t, flags=re.I)
    t = re.sub(r"\bart\.\s*(\d+)\s*°", r"art. \1º", t, flags=re.I)
    t = re.sub(r"\bArt\.\s*(\d+)\s+o\b", r"Art. \1º", t, flags=re.I)
    t = re.sub(r"\bart\.\s*(\d+)\s+o\b", r"art. \1º", t, flags=re.I)
    t = re.sub(r"\bart\.\s*(\d+)o\b", r"art. \1º", t, flags=re.I)
    t = re.sub(r"\bArt\.\s*(\d+)o\b", r"Art. \1º", t, flags=re.I)
    t = re.sub(r"\bParagrafo\s+unico\b", "Parágrafo único", t, flags=re.I)
    t = re.sub(r"\bparagrafo\s+unico\b", "parágrafo único", t, flags=re.I)
    t = re.sub(r"\bDecreto\s*-\s*Lei\b", "Decreto-Lei", t, flags=re.I)
    t = re.sub(r"\bLei\s+Complementar\s+n[º°.]?\s*", "Lei Complementar ", t, flags=re.I)
    t = re.sub(r"\bLei\s+n[º°.]?\s*", "Lei ", t, flags=re.I)
    t = re.sub(r"\bConstituicao\s+Federal\b", "Constituição Federal", t, flags=re.I)
    t = re.sub(r"\bRecurso\s+Extraordinario\b", "Recurso Extraordinário", t, flags=re.I)
    t = re.sub(r"\bRecurso\s+Ordinario\b", "Recurso Ordinário", t, flags=re.I)
    t = re.sub(r"\bRepercussao\s+Geral\b", "Repercussão Geral", t, flags=re.I)
    t = re.sub(r"\bRecurso\s+Repetitivo\b", "Recurso Repetitivo", t, flags=re.I)
    t = re.sub(r"\bTema\s+de\s+Repetitivo\b", "Tema de Repetitivo", t, flags=re.I)
    return t


def fix_crawl_phrasing(text: str) -> str:
    t = text
    t = re.sub(r"\b((?:nesta|desta|esta)\s+Lei)\s+(os|as)\b", r"\1, \2", t, flags=re.I)
    t = re.sub(
        r"\badministração\s+pública\s+(convênio|contrato)\b",
        r"administração pública, \1",
        t,
        flags=re.I,
    )
    t = re.sub(r"\bConsti\s+tui\b", "Constitui", t, flags=re.I)
    t = re.sub(r"\bConversacao\d*\b", "", t, flags=re.I)
    t = re.sub(r"\bnao\s+podera\b", "não poderá", t, flags=re.I)
    t = re.sub(r"\bnao\s+podem\b", "não podem", t, flags=re.I)
    t = re.sub(r"\bnao\s+se\s+aplica\b", "não se aplica", t, flags=re.I)
    t = re.sub(r"\bhao\s+crime\b", "há crime", t, flags=re.I)
    t = re.sub(r"\bnao\s+ha\b", "não há", t, flags=re.I)
    return t


def _glued_replacer(match: re.Match[str]) -> str:
    full = match.group(0)
    head = match.group(1)
    tail = match.group(2)
    if re.search(r"vincul$", head, re.I) and re.match(r"^ante$", tail, re.I):
        return full
    if re.search(r"inconform$", head, re.I) and re.match(r"^e$", tail, re.I):
        return full
    return f"{head} {tail}"


def split_stuck_words(text: str) -> str:
    t = text
    glued = sorted([*GLUED_LEGAL, *GLUED_PREPS], key=len, reverse=True)
    for w in glued:
        esc = re.escape(w)
        t = re.sub(
            rf"([a-záéíóúãõç]{{4,}})({esc})(?=\s|[.,;:)\\]\-]|$)",
            _glued_replacer,
            t,
            flags=re.I,
        )
    t = re.sub(r"([a-záéíóúãõç])([A-ZÁÉÍÓÚÃÕÇ])", r"\1 \2", t)
    return re.sub(r"[ \t]{2,}", " ", t)


def fix_broken_syllables(text: str) -> str:
    def _merge(m: re.Match[str]) -> str:
        bol, head, tail = m.group(1), m.group(2), m.group(3)
        if head.lower() in _SYLLABLE_NO_MERGE:
            return f"{bol}{head} {tail}"
        return f"{bol}{head}{tail}"

    return re.sub(
        r"(^|\n)([A-Za-zÁÉÍÓÚáéíóúÃÕÇãõç]{1,4})\s*\n+\s*([a-záéíóúãõç])",
        _merge,
        text,
        flags=re.M,
    )


def domain_for_doc_type(doc_type: str | None, source: str | None = None) -> Domain:
    dt = (doc_type or "").lower()
    if dt == "legislacao":
        return "legis"
    if dt in ("sumula", "jurisprudencia"):
        return "juris"
    src = (source or "").lower()
    if src in ("planalto", "rideel_vademecum", "agu"):
        return "legis"
    if src in ("trilhante_informativo", "trilhante"):
        return "juris"
    return "all"


def apply_pt_norma(text: str, *, domain: Domain = "all") -> str:
    """Aplica normalização de português jurídico (norma culta)."""
    if not text:
        return ""
    t = fix_mojibake(text)
    t = fix_broken_syllables(t)
    t = fix_legal_citations(t)
    t = fix_word_accents(t)
    t = split_stuck_words(t)
    t = fix_crawl_phrasing(t)
    if domain != "juris":
        t = fix_typography(t)
    else:
        t = re.sub(r"[ \t]{2,}", " ", t)
    t = normalize_lei_references(t)
    return t
