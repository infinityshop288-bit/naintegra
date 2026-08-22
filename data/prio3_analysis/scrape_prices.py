"""Scraping de precos historicos de PRIO3 (B3) e Brent (ultimos 5 anos).

Fonte: Yahoo Finance via yfinance.
- PRIO3.SA : acao ordinaria da PRIO S.A. na B3 (em BRL)
- BZ=F     : contrato futuro do petroleo Brent (em USD)
- USDBRL=X : cambio para conversao/normalizacao
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)

END = datetime.today()
START = END - timedelta(days=365 * 5 + 5)

TICKERS = {
    "PRIO3": "PRIO3.SA",
    "BRENT": "BZ=F",
    "USDBRL": "USDBRL=X",
}


def fetch(ticker: str) -> pd.DataFrame:
    print(f"Baixando {ticker} ...")
    df = yf.download(
        ticker,
        start=START.strftime("%Y-%m-%d"),
        end=END.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    return df


def main() -> None:
    frames = {}
    for name, tk in TICKERS.items():
        df = fetch(tk)
        path = OUT / f"raw_{name}.csv"
        df.to_csv(path, index=False)
        frames[name] = df
        print(f"  -> {name}: {len(df)} linhas | {df['Date'].min()} a {df['Date'].max()}")

    # Serie consolidada de fechamento (ajustado) por data
    def close_series(df: pd.DataFrame, name: str) -> pd.Series:
        s = df.set_index("Date")["Close"].rename(name)
        s.index = pd.to_datetime(s.index)
        return s

    merged = pd.concat(
        [close_series(frames[n], n) for n in TICKERS],
        axis=1,
    ).sort_index()
    merged = merged.ffill().dropna(how="all")
    merged.to_csv(OUT / "merged_close.csv")

    # Estatisticas resumidas
    stats = {}
    for name in ["PRIO3", "BRENT"]:
        s = merged[name].dropna()
        rets = s.pct_change().dropna()
        first, last = float(s.iloc[0]), float(s.iloc[-1])
        stats[name] = {
            "inicio": str(s.index[0].date()),
            "fim": str(s.index[-1].date()),
            "preco_inicial": round(first, 4),
            "preco_final": round(last, 4),
            "retorno_total_pct": round((last / first - 1) * 100, 2),
            "cagr_pct": round(((last / first) ** (1 / 5) - 1) * 100, 2),
            "vol_anualizada_pct": round(float(rets.std()) * (252 ** 0.5) * 100, 2),
            "max": round(float(s.max()), 4),
            "min": round(float(s.min()), 4),
            "max_data": str(s.idxmax().date()),
            "min_data": str(s.idxmin().date()),
        }

    # Correlacao entre retornos diarios de PRIO3 e Brent
    joint = merged[["PRIO3", "BRENT"]].dropna().pct_change().dropna()
    corr = float(joint["PRIO3"].corr(joint["BRENT"]))
    beta = float(joint.cov().loc["PRIO3", "BRENT"] / joint["BRENT"].var())
    stats["correlacao_prio3_brent_retornos_diarios"] = round(corr, 3)
    stats["beta_prio3_vs_brent"] = round(beta, 3)

    (OUT / "stats_prices.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
