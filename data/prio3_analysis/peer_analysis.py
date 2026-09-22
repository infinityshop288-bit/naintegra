"""Analise de uma acao do setor de oleo & gas (tecnicos + relativo a PRIO3/Brent).

Gera <ticker>_analysis.json com:
  - snapshot: preco, retornos (1m/3m/6m/12m/YTD), 52s high/low e distancias
  - tecnicos: MM50/MM200, distancia p/ MM200, tendencia, RSI(14), vol anualizada
  - relativo: correlacao e beta vs Brent e vs PRIO3 (retornos diarios)

Uso:  python peer_analysis.py PETR4 [BRAV3 ...]
Os precos vem do CSV raw_<TICKER>.csv quando existe; senao baixa do Yahoo e salva.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent

NOMES = {
    "PETR4": "Petrobras PN",
    "BRAV3": "Brava Energia",
    "PRIO3": "Prio S.A.",
}


def load_csv(csv: str) -> pd.Series:
    df = pd.read_csv(ROOT / csv)
    dcol = "Date" if "Date" in df.columns else df.columns[0]
    ccol = "Close" if "Close" in df.columns else ("close" if "close" in df.columns else None)
    df[dcol] = pd.to_datetime(df[dcol], errors="coerce", utc=True).dt.tz_localize(None)
    s = pd.to_numeric(df[ccol], errors="coerce")
    s.index = df[dcol]
    return s.dropna()


def load_prices(ticker: str) -> pd.Series:
    """Preços do ticker: baixa do Yahoo e usa o CSV local só como reserva.

    O CSV é cache, não fonte: tratá-lo como fonte congelava a análise no dia
    em que o arquivo foi criado.
    """
    csv = ROOT / f"raw_{ticker}.csv"
    reserva = load_csv(csv.name) if csv.is_file() else pd.Series(dtype=float)
    import yfinance as yf

    try:
        d = yf.download(f"{ticker}.SA", period="5y", interval="1d",
                        progress=False, auto_adjust=True)
        s = d["Close"].dropna()
    except Exception:  # noqa: BLE001
        s = pd.Series(dtype=float)
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    if not len(s):
        if not len(reserva):
            raise SystemExit(f"sem preços para {ticker} (Yahoo falhou e não há cache)")
        print(f"  [aviso] {ticker}: Yahoo sem dados, usando cache até {reserva.index[-1].date()}")
        return reserva
    s.index = pd.to_datetime(s.index).tz_localize(None)
    s.rename("Close").to_frame().to_csv(csv, index_label="Date")
    return s


def rsi(s: pd.Series, n: int = 14) -> float:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn
    return float((100 - 100 / (1 + rs)).iloc[-1])


def ret_since(s: pd.Series, days: int):
    if len(s) <= days:
        return None
    return round((s.iloc[-1] / s.iloc[-1 - days] - 1) * 100, 1)


def build(ticker: str) -> dict:
    px_s = load_prices(ticker)
    prio = load_prices("PRIO3")
    brent = load_csv("raw_BRENT.csv")

    px = float(px_s.iloc[-1])
    sma50 = float(px_s.rolling(50).mean().iloc[-1])
    sma200 = float(px_s.rolling(200).mean().iloc[-1])
    hi52 = float(px_s.iloc[-252:].max())
    lo52 = float(px_s.iloc[-252:].min())
    vol_an = float(px_s.pct_change().iloc[-252:].std() * np.sqrt(252) * 100)

    yr = px_s.index[-1].year
    ytd_base = px_s[px_s.index >= f"{yr}-01-01"]
    ytd = round((px / float(ytd_base.iloc[0]) - 1) * 100, 1) if len(ytd_base) else None

    def rel(other: pd.Series) -> dict:
        j = pd.concat([px_s.pct_change(), other.pct_change()], axis=1, join="inner").dropna()
        j = j.iloc[-252:]
        if len(j) < 30:
            return {"corr": None, "beta": None, "n": len(j)}
        x = j.iloc[:, 1]; y = j.iloc[:, 0]
        return {"corr": round(float(np.corrcoef(x, y)[0, 1]), 2),
                "beta": round(float(np.cov(y, x)[0, 1] / np.var(x)), 2),
                "n": int(len(j))}

    trend = "alta" if px > sma50 > sma200 else ("baixa" if px < sma50 < sma200 else "lateral")

    return {
        "ativo": ticker, "nome": NOMES.get(ticker, ticker),
        "atualizado": px_s.index[-1].strftime("%Y-%m-%d"),
        "snapshot": {
            "preco": round(px, 2),
            "ret_1m": ret_since(px_s, 21), "ret_3m": ret_since(px_s, 63),
            "ret_6m": ret_since(px_s, 126), "ret_12m": ret_since(px_s, 252), "ret_ytd": ytd,
            "high_52s": round(hi52, 2), "low_52s": round(lo52, 2),
            "dist_high_pct": round((px / hi52 - 1) * 100, 1),
            "dist_low_pct": round((px / lo52 - 1) * 100, 1),
        },
        "tecnicos": {
            "sma50": round(sma50, 2), "sma200": round(sma200, 2),
            "dist_sma200_pct": round((px / sma200 - 1) * 100, 1),
            "tendencia": trend, "rsi14": round(rsi(px_s), 1),
            "vol_anual_pct": round(vol_an, 1),
        },
        "relativo": {
            "vs_brent": rel(brent), "vs_prio3": rel(prio),
            "prio3_preco": round(float(prio.iloc[-1]), 2),
        },
    }


# painel, export e build já consomem brav_analysis.json (sem o "3")
ARQUIVO_LEGADO = {"BRAV3": "brav_analysis.json"}


def main() -> None:
    tickers = sys.argv[1:] or ["PETR4"]
    for tk in tickers:
        out = build(tk)
        path = ROOT / ARQUIVO_LEGADO.get(tk, f"{tk.lower()}_analysis.json")
        path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
        print(f"salvo {path.name} | {tk} R$ {out['snapshot']['preco']} · "
              f"tendência {out['tecnicos']['tendencia']}")


if __name__ == "__main__":
    main()
