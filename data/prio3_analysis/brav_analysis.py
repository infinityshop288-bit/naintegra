"""Analise da acao BRAV3 (Brava Energia) — tecnicos + comparacao com PRIO3/Brent.

Gera brav_analysis.json com:
  - snapshot: preco, retornos (1m/3m/6m/12m/YTD), 52s high/low e distancias
  - tecnicos: MM50/MM200, distancia p/ MM200, tendencia, RSI(14), vol anualizada
  - relativo: correlacao e beta de BRAV3 vs Brent e vs PRIO3 (retornos diarios)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent


def load(csv: str) -> pd.Series:
    df = pd.read_csv(ROOT / csv)
    dcol = "Date" if "Date" in df.columns else df.columns[0]
    ccol = "Close" if "Close" in df.columns else ("close" if "close" in df.columns else None)
    df[dcol] = pd.to_datetime(df[dcol], errors="coerce")
    s = pd.to_numeric(df[ccol], errors="coerce")
    s.index = df[dcol]
    return s.dropna()


def rsi(s: pd.Series, n: int = 14) -> float:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn
    return float((100 - 100 / (1 + rs)).iloc[-1])


def ret_since(s: pd.Series, days: int) -> float:
    if len(s) <= days:
        return None
    return round((s.iloc[-1] / s.iloc[-1 - days] - 1) * 100, 1)


def main() -> None:
    brav = load("raw_BRAV3.csv")
    prio = load("raw_PRIO3.csv")
    brent = load("raw_BRENT.csv")

    px = float(brav.iloc[-1])
    sma50 = float(brav.rolling(50).mean().iloc[-1])
    sma200 = float(brav.rolling(200).mean().iloc[-1])
    hi52 = float(brav.iloc[-252:].max())
    lo52 = float(brav.iloc[-252:].min())
    r = brav.pct_change()
    vol_an = float(r.iloc[-252:].std() * np.sqrt(252) * 100)

    # YTD
    yr = brav.index[-1].year
    ytd_base = brav[brav.index >= f"{yr}-01-01"]
    ytd = round((px / float(ytd_base.iloc[0]) - 1) * 100, 1) if len(ytd_base) else None

    # relativo (alinha datas)
    def rel(other: pd.Series):
        j = pd.concat([brav.pct_change(), other.pct_change()], axis=1, join="inner").dropna()
        j = j.iloc[-252:]
        if len(j) < 30:
            return {"corr": None, "beta": None, "n": len(j)}
        x = j.iloc[:, 1]; y = j.iloc[:, 0]
        corr = float(np.corrcoef(x, y)[0, 1])
        beta = float(np.cov(y, x)[0, 1] / np.var(x))
        return {"corr": round(corr, 2), "beta": round(beta, 2), "n": int(len(j))}

    trend = "alta" if px > sma50 > sma200 else ("baixa" if px < sma50 < sma200 else "lateral")

    out = {
        "ativo": "BRAV3", "nome": "Brava Energia",
        "atualizado": brav.index[-1].strftime("%Y-%m-%d"),
        "snapshot": {
            "preco": round(px, 2),
            "ret_1m": ret_since(brav, 21), "ret_3m": ret_since(brav, 63),
            "ret_6m": ret_since(brav, 126), "ret_12m": ret_since(brav, 252), "ret_ytd": ytd,
            "high_52s": round(hi52, 2), "low_52s": round(lo52, 2),
            "dist_high_pct": round((px / hi52 - 1) * 100, 1),
            "dist_low_pct": round((px / lo52 - 1) * 100, 1),
        },
        "tecnicos": {
            "sma50": round(sma50, 2), "sma200": round(sma200, 2),
            "dist_sma200_pct": round((px / sma200 - 1) * 100, 1),
            "tendencia": trend, "rsi14": round(rsi(brav), 1),
            "vol_anual_pct": round(vol_an, 1),
        },
        "relativo": {
            "vs_brent": rel(brent), "vs_prio3": rel(prio),
            "prio3_preco": round(float(prio.iloc[-1]), 2),
        },
    }
    (ROOT / "brav_analysis.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
