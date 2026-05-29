"""Catálogo e fetch de legislação consolidada do Planalto para o Lex."""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

# Leis acompanhadas pelo job semanal (Planalto — texto compilado quando existir).
PLANALTO_LEGIS_CATALOG: list[dict[str, str]] = [
    {
        "url": "http://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
        "titulo": "Constituição Federal de 1988",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm",
        "titulo": "Lei nº 10.406/2002 — Código Civil",
        "secao": "Civil e Trabalho",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/decreto-lei/del2848.htm",
        "titulo": "Decreto-Lei nº 2.848/1940 — Código Penal",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/decreto-lei/del3689.htm",
        "titulo": "Decreto-Lei nº 3.689/1941 — Código de Processo Penal",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11340.htm",
        "titulo": "Lei nº 11.340/2006 — Lei Maria da Penha",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l7210.htm",
        "titulo": "Lei nº 7.210/1984 — Lei de Execução Penal",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l8072.htm",
        "titulo": "Lei nº 8.072/1990 — Crimes Hediondos",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12830.htm",
        "titulo": "Lei nº 12.830/2013 — Investigação Criminal",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm",
        "titulo": "Lei nº 13.105/2015 — Código de Processo Civil",
        "secao": "Civil e Trabalho",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11343.htm",
        "titulo": "Lei nº 11.343/2006 — Lei de Drogas",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
        "titulo": "Lei nº 8.429/1992 — Improbidade Administrativa",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9784.htm",
        "titulo": "Lei nº 9.784/1999 — Processo Administrativo Federal",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9882.htm",
        "titulo": "Lei nº 9.882/1999 — ADI, ADC, ADPF e Mandado de Injunção",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/lei/l13300.htm",
        "titulo": "Lei nº 13.300/2016 — Mandado de Injunção",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l8249.htm",
        "titulo": "Lei nº 8.249/1991 — Nota do Tesouro Nacional (NTN)",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l8666cons.htm",
        "titulo": "Lei nº 8.666/1993 — Licitações e Contratos",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l8078.htm",
        "titulo": "Lei nº 8.078/1990 — Código de Defesa do Consumidor",
        "secao": "Civil e Trabalho",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9514.htm",
        "titulo": "Lei nº 9.514/1997 — Alienação fiduciária",
        "secao": "Civil e Trabalho",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l6858.htm",
        "titulo": "Lei nº 6.858/1980 — Pagamento a terceiros",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9307.htm",
        "titulo": "Lei nº 9.307/1996 — Lei de Arbitragem",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/2003/l10.741.htm",
        "titulo": "Lei 10.741/2003 — Estatuto do Idoso",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/2003/l10.826.htm",
        "titulo": "Lei 10.826/2003 — Estatuto do Desarmamento",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l6015consolidado.htm",
        "titulo": "Lei 6.015/1973 — Lei de Registros Públicos",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l6404consol.htm",
        "titulo": "Lei 6.404/1976 — Lei das S.A.",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l8036consol.htm",
        "titulo": "Lei 8.036/1990 — FGTS",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l8069.htm",
        "titulo": "Lei 8.069/1990 — ECA",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2007-2010/2008/lei/l11671.htm",
        "titulo": "Lei 11.671/2008 — Presídios federais",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/l14965.htm",
        "titulo": "Lei 14.965/2024 — Concursos públicos",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/l15040.htm",
        "titulo": "Lei 15.040/2024 — Lei do Contrato de Seguro",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/l15272.htm",
        "titulo": "Lei 15.272/2025 — Atualizações processuais penais",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/lei/l15358.htm",
        "titulo": "Lei 15.358/2026 — Marco Legal do Combate ao Crime Organizado",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/lei/l15397.htm",
        "titulo": "Lei 15.397/2026 — Aumento de penas (crimes patrimoniais)",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/decreto-lei/del4657.htm",
        "titulo": "Decreto-Lei 4.657/1942 — LINDB",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9868.htm",
        "titulo": "Lei 9.868/1999 — ADI e ADC",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2007-2010/2010/lei/l12016.htm",
        "titulo": "Lei 12.016/2009 — Mandado de Segurança",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l4717.htm",
        "titulo": "Lei 4.717/1965 — Ação Popular",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm",
        "titulo": "Lei 14.133/2021 — Nova Lei de Licitações",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm",
        "titulo": "Lei 12.527/2011 — LAI",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/decreto-lei/del3365.htm",
        "titulo": "Decreto-Lei 3.365/1941 — Desapropriação",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l8625.htm",
        "titulo": "Lei 8.625/1993 — Lei Orgânica Nacional do MP",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9455.htm",
        "titulo": "Lei 9.455/1997 — Tortura",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l7716.htm",
        "titulo": "Lei 7.716/1989 — Crimes de Racismo",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9605.htm",
        "titulo": "Lei 9.605/1998 — Crimes Ambientais",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l8137.htm",
        "titulo": "Lei 8.137/1990 — Crimes contra a Ordem Tributária",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l7492.htm",
        "titulo": "Lei 7.492/1986 — Crimes contra o SFN",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9296.htm",
        "titulo": "Lei 9.296/1996 — Interceptação Telefônica",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9613.htm",
        "titulo": "Lei 9.613/1998 — Lavagem de Capitais",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12850.htm",
        "titulo": "Lei 12.850/2013 — Organização Criminosa",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2019-2022/2019/lei/l13869.htm",
        "titulo": "Lei 13.869/2019 — Abuso de Autoridade",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9503.htm",
        "titulo": "Lei 9.503/1997 — CTB",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9099.htm",
        "titulo": "Lei 9.099/1995 — Juizados Especiais",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/lei/l13260.htm",
        "titulo": "Lei 13.260/2016 — Terrorismo",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/l14811.htm",
        "titulo": "Lei 14.811/2024 — Bullying e cyberbullying",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/lei/l14597.htm",
        "titulo": "Lei 14.597/2023 — Lei Geral do Esporte",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/lei/l14344.htm",
        "titulo": "Lei 14.344/2022 — Lei Henry Borel",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2017/lei/l13431.htm",
        "titulo": "Lei 13.431/2017 — Depoimento Especial",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2019-2022/2019/lei/l13964.htm",
        "titulo": "Lei 13.964/2019 — Pacote Anticrime",
        "secao": "Penal e Processual",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l8245.htm",
        "titulo": "Lei 8.245/1991 — Locações",
        "secao": "Civil e Trabalho",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2004-2006/2005/lei/l11101.htm",
        "titulo": "Lei 11.101/2005 — Recuperação Judicial e Falência",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l7347.htm",
        "titulo": "Lei 7.347/1985 — Ação Civil Pública",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12852.htm",
        "titulo": "Lei 12.852/2013 — Estatuto da Juventude",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm",
        "titulo": "Lei 13.146/2015 — Estatuto da Pessoa com Deficiência",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l8080.htm",
        "titulo": "Lei 8.080/1990 — SUS",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l6938.htm",
        "titulo": "Lei 6.938/1981 — PNMA",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/lei/l12651.htm",
        "titulo": "Lei 12.651/2012 — Código Florestal",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2007-2010/2007/lei/l11445.htm",
        "titulo": "Lei 11.445/2007 — Saneamento Básico",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14119.htm",
        "titulo": "Lei 14.119/2021 — Pagamento por Serviços Ambientais",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l10257.htm",
        "titulo": "Lei 10.257/2001 — Estatuto da Cidade",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l6766.htm",
        "titulo": "Lei 6.766/1979 — Parcelamento do Solo",
        "secao": "Legislação Especial",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12846.htm",
        "titulo": "Lei 12.846/2013 — Lei Anticorrupção",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l4737.htm",
        "titulo": "Lei 4.737/1965 — Código Eleitoral",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9504.htm",
        "titulo": "Lei 9.504/1997 — Lei das Eleições",
        "secao": "Constituição e Adm.",
    },
    {
        "url": "http://www.planalto.gov.br/ccivil_03/leis/l9985.htm",
        "titulo": "Lei 9.985/2000 — SNUC",
        "secao": "Legislação Especial",
    },
]

REVOKE_TAGS = frozenset({"s", "del", "strike"})
BLOCK_BREAK_TAGS = frozenset({"p", "br", "div", "h1", "h2", "h3", "h4", "li", "tr", "blockquote", "hr"})


@dataclass
class FetchResult:
    url: str
    text: str
    content_hash: str
    char_count: int


class _PlanaltoHtmlToLex(HTMLParser):
    """Converte HTML Planalto em texto Lex com ~~revogado~~ e quebras estruturais."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0
        self._revoke_stack: list[str] = []

    @staticmethod
    def _attrs_map(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {k: (v or "") for k, v in attrs}

    def _strikethrough_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> str | None:
        t = tag.lower()
        if t in REVOKE_TAGS:
            return t
        if t == "span":
            style = self._attrs_map(attrs).get("style", "").lower()
            if "line-through" in style:
                return "span-strike"
        return None

    def _open_revoke(self, marker: str) -> None:
        self._revoke_stack.append(marker)
        if len(self._revoke_stack) == 1:
            self._parts.append("~~")

    def _close_revoke(self, marker: str) -> None:
        if not self._revoke_stack:
            return
        if self._revoke_stack[-1] != marker:
            # HTML Planalto costuma aninhar <strike> dentro de <span style="line-through"> mal fechados.
            while self._revoke_stack and self._revoke_stack[-1] != marker:
                self._revoke_stack.pop()
                if not self._revoke_stack:
                    self._parts.append("~~")
            if not self._revoke_stack:
                return
        self._revoke_stack.pop()
        if not self._revoke_stack:
            self._parts.append("~~")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t in ("script", "style", "noscript"):
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        strike = self._strikethrough_tag(t, attrs)
        if strike:
            self._open_revoke(strike)
            return
        if t in BLOCK_BREAK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("script", "style", "noscript"):
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if t in REVOKE_TAGS:
            self._close_revoke(t)
            return
        if t == "span":
            self._close_revoke("span-strike")
            return
        if t in BLOCK_BREAK_TAGS:
            while self._revoke_stack:
                self._revoke_stack.pop()
                self._parts.append("~~")

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not data:
            return
        self._parts.append(data)

    def text(self) -> str:
        while self._revoke_stack:
            self._revoke_stack.pop()
            self._parts.append("~~")
        raw = "".join(self._parts)
        raw = raw.replace("\xa0", " ")
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        raw = re.sub(r"[ \t]{2,}", " ", raw)
        return raw.strip()


def normalize_planalto_article_refs(text: str) -> str:
    """Converte numeração Planalto com milhar (Art. 1.026) para Art. 1026."""

    def _repl(match: re.Match[str]) -> str:
        return f"Art. {match.group(1).replace('.', '')}"

    return re.sub(r"Art\.\s*(\d{1,3}(?:\.\d{3})+)(?!\d)", _repl, text or "", flags=re.I)


def html_to_lex_text(html: str) -> str:
    parser = _PlanaltoHtmlToLex()
    parser.feed(html)
    return normalize_planalto_article_refs(parser.text())


def normalize_for_hash(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    return t


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_for_hash(text).encode("utf-8")).hexdigest()


def fetch_planalto_html(url: str, *, timeout: int = 120) -> str:
    raw = subprocess.check_output(
        ["curl", "-sL", "-A", "Mozilla/5.0 (compatible; NaIntegraLex/1.0)", url],
        timeout=timeout,
    )
    for encoding in ("iso-8859-1", "latin-1", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("iso-8859-1", errors="replace")


def fetch_planalto_text(url: str, *, timeout: int = 120) -> FetchResult:
    html = fetch_planalto_html(url, timeout=timeout)
    text = html_to_lex_text(html)
    return FetchResult(
        url=url,
        text=text,
        content_hash=content_hash(text),
        char_count=len(text),
    )


def catalog_entry(url: str, titulo: str, secao: str) -> dict[str, str]:
    return {"url": url, "titulo": titulo, "secao": secao}


def merge_catalog(*extra: dict[str, str]) -> list[dict[str, str]]:
    """Une catálogo estático com entradas descobertas (dedupe por URL normalizada)."""
    from .norma_chunks import normalize_norma_url

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in [*PLANALTO_LEGIS_CATALOG, *extra]:
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        key = normalize_norma_url(url)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "url": url,
                "titulo": str(item.get("titulo") or key),
                "secao": str(item.get("secao") or "Legislação Especial"),
            }
        )
    return out


def discovered_catalog_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    from .norma_chunks import legis_meta_from_url, normalize_norma_url

    extra: list[dict[str, str]] = []
    for row in rows:
        url = normalize_norma_url(str(row.get("url") or row.get("doc_key") or ""))
        if not url or "planalto.gov.br" not in url.lower():
            continue
        meta = legis_meta_from_url(url)
        extra.append(
            catalog_entry(
                url,
                str(row.get("metadata", {}).get("titulo") or meta.get("titulo") or url),
                str(row.get("metadata", {}).get("secao_lei_seca") or meta.get("secao_lei_seca") or "Legislação Especial"),
            )
        )
    return extra
