"""Fatos Relevantes + anuncios de Resultados das 15 empresas do universo.

Fonte: Portal de Dados Abertos da CVM (IPE - Informacoes Periodicas e Eventuais),
que reune TODOS os documentos protocolados por companhias abertas, com categoria,
tipo, assunto, data e link de download.

Para cada empresa:
  - fatos: ultimos Fatos Relevantes (Categoria == "Fato Relevante");
  - resultados: anuncios de resultados dos ultimos 2 anos (releases/press-release,
    ITR - Demonstracoes Financeiras Intermediarias, DFP/Relatorio Anual e
    apresentacoes de resultado).

O CNPJ de cada ticker e resolvido dinamicamente pelo nome na base (escolhendo,
entre as companhias que casam com a palavra-chave, a que tem MAIS documentos —
que e sempre a companhia listada principal). Saida: fatos_relevantes_multi.json.
"""
from __future__ import annotations

import io
import json
import re
import unicodedata
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

from universe import UNIVERSE

OUT = Path(__file__).resolve().parent
BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{y}.zip"
HEADERS = {"User-Agent": "Mozilla/5.0 (research; prio3-analysis)"}
YEARS = [date.today().year - 2, date.today().year - 1, date.today().year]

# palavra(s)-chave p/ localizar a companhia na base CVM (por ticker); a 1a que casar
# e tiver mais documentos vence. Ordem = prioridade.
KEYWORDS = {
    "PRIO3": ["PRIO", "PETRO RIO"],
    "BRAV3": ["BRAVA ENERGIA", "3R PETROLEUM", "ENAUTA"],
    "MGLU3": ["MAGAZINE LUIZA", "MAGAZ LUIZA"],
    "LREN3": ["LOJAS RENNER", "RENNER"],
    "EQTL3": ["EQUATORIAL"],
    "CMIG4": ["CEMIG", "ENERGETICA DE MINAS GERAIS"],
    "ITUB4": ["ITAU UNIBANCO"],
    "BBDC4": ["BCO BRADESCO", "BRADESCO"],
    "BBAS3": ["BCO BRASIL", "BANCO DO BRASIL"],
    "BBSE3": ["BB SEGURIDADE"],
    "PSSA3": ["PORTO SEGURO"],
    "VALE3": ["VALE S.A", "VALE S/A", "VALE"],
    "SUZB3": ["SUZANO S.A", "SUZANO"],
    "ABEV3": ["AMBEV"],
    "MBRF3": ["MBRF", "MARFRIG", "BRF S.A"],
    "CYRE3": ["CYRELA BRAZIL", "CYRELA"],
    "MRVE3": ["MRV ENGENHARIA", "MRV E PARTICIPACOES", "MRV"],
    "DIRR3": ["DIRECIONAL ENGENHARIA", "DIRECIONAL"],
    "CURY3": ["CURY CONSTRUTORA", "CURY"],
    "WEGE3": ["WEG S.A", "WEG SA", "WEG"],
    "CSNA3": ["SIDERURGICA NACIONAL", "CSN", "CIA SIDERURGICA"],
}


def deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c)).upper()


def load_ipe() -> pd.DataFrame:
    frames = []
    for y in YEARS:
        url = BASE.format(y=y)
        try:
            r = requests.get(url, headers=HEADERS, timeout=90); r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            print(f"  falhou {y}: {e}"); continue
        c = r.content
        if c[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(c)) as z:
                c = z.read([n for n in z.namelist() if n.endswith(".csv")][0])
        df = pd.read_csv(io.BytesIO(c), sep=";", encoding="latin-1", dtype=str)
        df.columns = [x.strip() for x in df.columns]
        frames.append(df)
        print(f"  IPE {y}: {len(df)} docs")
    ipe = pd.concat(frames, ignore_index=True)
    for col in ("Nome_Companhia", "CNPJ_Companhia", "Categoria", "Tipo", "Assunto", "Data_Entrega", "Link_Download"):
        if col not in ipe.columns:
            ipe[col] = ""
    ipe["_nome_norm"] = ipe["Nome_Companhia"].map(deaccent)
    ipe["Data_Entrega"] = ipe["Data_Entrega"].astype(str).str[:10]
    return ipe


def resolve_cnpj(ipe: pd.DataFrame, keywords: list[str]):
    counts = ipe.groupby(["CNPJ_Companhia", "Nome_Companhia", "_nome_norm"]).size().reset_index(name="n")
    for kw in keywords:
        kwn = deaccent(kw)
        cand = counts[counts["_nome_norm"].str.contains(re.escape(kwn), na=False)]
        if kwn == "BRADESCO":  # evita BRADESPAR
            cand = cand[~cand["_nome_norm"].str.contains("BRADESPAR", na=False)]
        if not cand.empty:
            best = cand.sort_values("n", ascending=False).iloc[0]
            return best["CNPJ_Companhia"], best["Nome_Companhia"]
    return None, None


EN_MARK = re.compile(r"(ingl[eê]s|english|quarterly information|\(en\))", re.I)
RESULT_TIPO_RE = re.compile(r"(press-?release|demonstra[cç][oõ]es financeiras|intermedi|"
                            r"relat[oó]rio anual|balan[cç]o)", re.I)
RESULT_ASSUNTO = re.compile(r"(release de resultad|press-?release|divulga[cç][aã]o de resultad|"
                            r"resultado \d|demonstra[cç][oõ]es (financ|cont)|desempenho|balan[cç]o|"
                            r"informa[cç][oõ]es trimestrais|\bITR\b|\bDFP\b|apresenta[cç][aã]o.*resultad)", re.I)
PERIODO_RE = re.compile(r"(\d{1,2}T\d{2,4}|\b20\d{2}\b)")


def is_english_only(assunto) -> bool:
    a = "" if assunto is None or isinstance(assunto, float) else str(assunto)
    return bool(EN_MARK.search(a)) and "portugu" not in a.lower()


def classify(tipo: str, assunto: str) -> str:
    t = "" if tipo is None or isinstance(tipo, float) else str(tipo)
    a = "" if assunto is None or isinstance(assunto, float) else str(assunto)
    ta = (t + " " + a)
    if re.search(r"apresenta", a, re.I):
        return "Apresentação"
    if re.search(r"intermedi|condensad|\bITR\b|trimestr|\dT\d", ta, re.I):
        return "ITR (trimestral)"
    if re.search(r"anua(l|is)|\bDFP\b|relat[oó]rio anual", ta, re.I):
        return "DFP (anual)"
    return "Release"


def clean_txt(s):
    if s is None or isinstance(s, float):
        return ""
    return re.sub(r"\s+", " ", str(s).replace("&amp", "&")).strip()


def dedupe(rows, keyfn=None):
    seen, out = set(), []
    for r in rows:
        key = keyfn(r) if keyfn else (r["data"], re.sub(r"\s*\((ingl|port).*?\)", "", r["assunto"], flags=re.I).lower()[:60])
        if key in seen:
            continue
        seen.add(key); out.append(r)
    return out


def main() -> None:
    print("Baixando IPE CVM…")
    ipe = load_ipe()
    cutoff = (date.today() - timedelta(days=730)).isoformat()
    empresas = {}
    for tk, (nome, setor, root) in UNIVERSE.items():
        cnpj, nome_cvm = resolve_cnpj(ipe, KEYWORDS[tk])
        if not cnpj:
            print(f"  {tk}: CNPJ nao resolvido"); empresas[tk] = {"nome": nome, "setor": setor, "erro": "nao localizado"}
            continue
        sub = ipe[ipe["CNPJ_Companhia"] == cnpj].copy()
        sub = sub.sort_values("Data_Entrega", ascending=False)

        # Fatos Relevantes
        fr = sub[sub["Categoria"].str.contains("Fato Relevante", case=False, na=False)]
        fr = fr[~fr["Assunto"].map(is_english_only)]
        fatos = dedupe([{"data": r["Data_Entrega"], "assunto": clean_txt(r["Assunto"]) or "(sem assunto)",
                         "tipo": clean_txt(r["Tipo"]), "link": r["Link_Download"]}
                        for _, r in fr.iterrows()])

        # Resultados (ultimos 2 anos)
        rr = sub[sub["Data_Entrega"] >= cutoff]
        mask = (rr["Categoria"].str.contains("Dados Econômico", na=False) &
                (rr["Tipo"].astype(str).str.contains(RESULT_TIPO_RE, na=False)
                 | rr["Assunto"].astype(str).str.contains(RESULT_ASSUNTO, na=False))) \
            | (rr["Categoria"].str.contains("Comunicado ao Mercado", na=False) &
               rr["Assunto"].astype(str).str.contains(r"apresenta[cç][aã]o.*resultad", case=False, na=False))
        rr = rr[mask]
        rr = rr[~rr["Assunto"].map(is_english_only)]

        def periodo_of(txt):
            m = PERIODO_RE.search(txt or "")
            return m.group(0) if m else None

        rows = [{"data": r["Data_Entrega"], "assunto": clean_txt(r["Assunto"]) or clean_txt(r["Tipo"]),
                 "categoria": classify(r["Tipo"], r["Assunto"]),
                 "periodo": periodo_of(clean_txt(r["Assunto"])),
                 "link": r["Link_Download"]} for _, r in rr.iterrows()]
        # dedup: 1 doc por (periodo, tipo-de-doc); sem periodo cai no fallback data+assunto
        resultados = dedupe(rows, keyfn=lambda r: (r["periodo"], r["categoria"]) if r["periodo"] else (r["data"], r["assunto"][:50]))

        empresas[tk] = {
            "nome": nome, "setor": setor, "cnpj": cnpj, "nome_cvm": clean_txt(nome_cvm),
            "n_fatos_2anos": len(fatos), "n_resultados_2anos": len(resultados),
            "fatos": fatos[:6], "resultados": resultados[:10],
        }
        print(f"  {tk:<7}{clean_txt(nome_cvm)[:34]:<35} fatos={len(fatos):>3} resultados={len(resultados):>3}")

    out = {"atualizado": date.today().isoformat(), "janela_resultados": "24 meses",
           "fonte": "CVM — Portal de Dados Abertos (IPE)", "empresas": empresas}
    (OUT / "fatos_relevantes_multi.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print("\nsalvo fatos_relevantes_multi.json |", len(empresas), "empresas")


if __name__ == "__main__":
    main()
