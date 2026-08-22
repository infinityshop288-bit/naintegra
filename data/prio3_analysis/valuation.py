"""Coleta metricas de valuation (yfinance) + ITR trimestral (CVM) e calcula preco justo."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

OUT = Path(__file__).resolve().parent
CD_CVM = "22187"
HEADERS = {"User-Agent": "Mozilla/5.0 (research)"}


def yf_info() -> dict:
    t = yf.Ticker("PRIO3.SA")
    info = t.info
    keys = [
        "currentPrice", "sharesOutstanding", "marketCap", "enterpriseValue",
        "enterpriseToEbitda", "trailingPE", "forwardPE", "priceToBook",
        "targetMeanPrice", "targetMedianPrice", "targetHighPrice", "targetLowPrice",
        "numberOfAnalystOpinions", "recommendationKey", "ebitda", "totalDebt", "totalCash",
        "bookValue", "returnOnEquity", "dividendYield",
    ]
    out = {k: info.get(k) for k in keys}
    return out


def _norm(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lstrip("0")


def load_member(zbytes: bytes, needle: str):
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        names = [n for n in z.namelist() if needle in n]
        if not names:
            return None
        return pd.read_csv(io.BytesIO(z.read(names[0])), sep=";", encoding="latin-1", dtype=str)


def itr_latest() -> dict:
    """Ultimo trimestre disponivel (ITR 2026)."""
    url = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_2026.zip"
    r = requests.get(url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    z = r.content
    dre = load_member(z, "itr_cia_aberta_DRE_con_")
    dfc = load_member(z, "itr_cia_aberta_DFC_MI_con_")
    bpa = load_member(z, "itr_cia_aberta_BPA_con_")
    bpp = load_member(z, "itr_cia_aberta_BPP_con_")

    def val(df, code):
        if df is None:
            return None
        sub = df[(_norm(df["CD_CVM"]) == CD_CVM) & (df["ORDEM_EXERC"] == "ÚLTIMO") & (df["CD_CONTA"] == code)]
        if sub.empty:
            return None
        sub = sub.sort_values("DT_FIM_EXERC")
        return float(sub["VL_CONTA"].iloc[-1].replace(",", "."))

    def val_desc(df, kw):
        if df is None:
            return None
        sub = df[(_norm(df["CD_CVM"]) == CD_CVM) & (df["ORDEM_EXERC"] == "ÚLTIMO")
                 & df["DS_CONTA"].str.contains(kw, case=False, na=False)]
        if sub.empty:
            return None
        last = sub["DT_FIM_EXERC"].max()
        sub = sub[sub["DT_FIM_EXERC"] == last]
        return float(sum(float(x.replace(",", ".")) for x in sub["VL_CONTA"]))

    periodo = None
    if dre is not None:
        sub = dre[(_norm(dre["CD_CVM"]) == CD_CVM) & (dre["ORDEM_EXERC"] == "ÚLTIMO")]
        if not sub.empty:
            periodo = {"ini": sub["DT_INI_EXERC"].max(), "fim": sub["DT_FIM_EXERC"].max()}

    receita = val(dre, "3.01")
    ebit = val(dre, "3.05")
    lucro = val(dre, "3.11") or val(dre, "3.09")
    da = val_desc(dfc, "Deprecia")
    ebitda = (ebit + da) if (ebit is not None and da is not None) else None
    caixa = val(bpa, "1.01.01")
    dc = val(bpp, "2.01.04")
    dnc = val(bpp, "2.02.01")
    divida = (dc or 0) + (dnc or 0) if (dc or dnc) else None
    dl = (divida - caixa) if (divida is not None and caixa is not None) else None
    return {
        "periodo": periodo, "receita": receita, "ebit": ebit, "ebitda": ebitda,
        "lucro_liquido": lucro, "divida_bruta": divida, "caixa": caixa, "divida_liquida": dl,
    }


def main() -> None:
    info = yf_info()
    print("== yfinance info ==")
    print(json.dumps(info, indent=2, ensure_ascii=False))
    try:
        itr = itr_latest()
    except Exception as e:  # noqa: BLE001
        itr = {"erro": str(e)}
    print("\n== ITR 2026 (ultimo periodo) ==")
    print(json.dumps(itr, indent=2, ensure_ascii=False))

    (OUT / "valuation_raw.json").write_text(json.dumps({"yf": info, "itr": itr}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
