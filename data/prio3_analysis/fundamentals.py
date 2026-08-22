"""Fundamentos DIVULGADOS pela PRIO nas demonstracoes financeiras (CVM DFP/ITR).

Fonte oficial: Portal de Dados Abertos da CVM.
- DFP (anual): https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_YYYY.zip
Extrai da DRE e do Balanco consolidados: receita, resultado operacional (EBIT),
lucro liquido, divida bruta, caixa e divida liquida.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).resolve().parent
CD_CVM = "022187"  # PRIO S.A. (com zero a esquerda no dataset da CVM)
HEADERS = {"User-Agent": "Mozilla/5.0 (research)"}
DFP = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{y}.zip"
YEARS = range(2021, 2026)


def load_member(zbytes: bytes, needle: str) -> pd.DataFrame | None:
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        names = [n for n in z.namelist() if needle in n]
        if not names:
            return None
        return pd.read_csv(io.BytesIO(z.read(names[0])), sep=";", encoding="latin-1", dtype=str)


def _norm(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lstrip("0")


def get_val(df: pd.DataFrame, code: str) -> float | None:
    """Valor da conta 'code' no exercicio ULTIMO, consolidado, para o CD_CVM."""
    sub = df[(_norm(df["CD_CVM"]) == CD_CVM.lstrip("0")) & (df["ORDEM_EXERC"] == "ÚLTIMO") & (df["CD_CONTA"] == code)]
    if sub.empty:
        return None
    sub = sub.sort_values("DT_FIM_EXERC")
    return float(sub["VL_CONTA"].iloc[-1].replace(",", "."))


def get_val_by_desc(df: pd.DataFrame | None, keyword: str) -> float | None:
    """Soma valores cujo DS_CONTA contem keyword (ULTIMO, consolidado)."""
    if df is None:
        return None
    sub = df[(_norm(df["CD_CVM"]) == CD_CVM.lstrip("0")) & (df["ORDEM_EXERC"] == "ÚLTIMO")
             & df["DS_CONTA"].str.contains(keyword, case=False, na=False)]
    if sub.empty:
        return None
    last = sub["DT_FIM_EXERC"].max()
    sub = sub[sub["DT_FIM_EXERC"] == last]
    return float(sum(float(x.replace(",", ".")) for x in sub["VL_CONTA"]))


def main() -> None:
    rows = []
    for y in YEARS:
        print(f"DFP {y} ...")
        try:
            r = requests.get(DFP.format(y=y), headers=HEADERS, timeout=120)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            print("  falhou", e)
            continue
        z = r.content
        dre = load_member(z, "dfp_cia_aberta_DRE_con_")
        bpa = load_member(z, "dfp_cia_aberta_BPA_con_")
        bpp = load_member(z, "dfp_cia_aberta_BPP_con_")
        if dre is None:
            continue

        dfc = load_member(z, "dfp_cia_aberta_DFC_MI_con_")
        moeda = None
        escala = None
        sub = dre[_norm(dre["CD_CVM"]) == CD_CVM.lstrip("0")]
        if not sub.empty:
            moeda = sub["MOEDA"].iloc[0]
            escala = sub["ESCALA_MOEDA"].iloc[0]

        receita = get_val(dre, "3.01")          # Receita de venda
        ebit = get_val(dre, "3.05")             # Resultado antes do resultado financeiro e tributos
        lucro = get_val(dre, "3.11")            # Lucro/prejuizo consolidado do periodo
        if lucro is None:
            lucro = get_val(dre, "3.09")
        dep_amort = get_val_by_desc(dfc, "Deprecia")  # depreciacao/amortizacao (DFC MI)
        ebitda = (ebit + dep_amort) if (ebit is not None and dep_amort is not None) else None

        caixa = get_val(bpa, "1.01.01") if bpa is not None else None
        div_circ = get_val(bpp, "2.01.04") if bpp is not None else None      # Emprestimos circulante
        div_ncirc = get_val(bpp, "2.02.01") if bpp is not None else None     # Emprestimos nao circulante
        divida_bruta = None
        if div_circ is not None or div_ncirc is not None:
            divida_bruta = (div_circ or 0) + (div_ncirc or 0)
        div_liq = None
        if divida_bruta is not None and caixa is not None:
            div_liq = divida_bruta - caixa

        rows.append({
            "ano": y,
            "moeda": moeda,
            "escala": escala if not sub.empty else None,
            "receita": receita,
            "ebit": ebit,
            "dep_amort": dep_amort,
            "ebitda": ebitda,
            "lucro_liquido": lucro,
            "divida_bruta": divida_bruta,
            "caixa": caixa,
            "divida_liquida": div_liq,
        })
        print("  ", rows[-1])

    (OUT / "fundamentals.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print("\nOK fundamentals.json")


if __name__ == "__main__":
    main()
