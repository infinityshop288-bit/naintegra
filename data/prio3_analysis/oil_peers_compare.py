"""Comparativo PRIO3 × Petrobras (PETR3) × Chevron (CVX) vs Brent.

Analisa:
  - evolucao indexada (base 100) e retornos acumulados
  - efeito diario quando Brent SOBE vs CAIR (media, mediana, taxa de acerto)
  - beta e correlacao vs Brent (252 pregões)
  - serie diaria recente (ultimos 90 pregões) para grafico de efeito Brent
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
TICKERS = {
    "PRIO3": "PRIO3.SA",
    "PETR3": "PETR3.SA",
    "CVX": "CVX",
    "BRENT": "BZ=F",
}
LABELS = {"PRIO3": "PRIO3", "PETR3": "Petrobras", "CVX": "Chevron", "BRENT": "Brent"}


def fetch_all(period: str = "5y") -> pd.DataFrame:
    syms = list(TICKERS.values())
    d = yf.download(syms, period=period, interval="1d", progress=False,
                    auto_adjust=True, group_by="ticker", threads=True)
    cols = {}
    for k, sym in TICKERS.items():
        try:
            sub = d[sym] if isinstance(d.columns, pd.MultiIndex) else d
            s = sub["Close"].dropna()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            cols[k] = s
        except Exception:  # noqa: BLE001
            pass
    df = pd.concat(cols, axis=1).sort_index().dropna(how="any")
    return df


def brent_effect(rets: pd.DataFrame) -> dict:
    b = rets["BRENT"]
    out = {}
    for col in ["PRIO3", "PETR3", "CVX"]:
        s = rets[col]
        up = b > 0.001
        dn = b < -0.001
        flat = ~up & ~dn
        out[col] = {
            "brent_alta": {
                "n": int(up.sum()),
                "media_pct": round(float(s[up].mean()) * 100, 3),
                "mediana_pct": round(float(s[up].median()) * 100, 3),
                "acerto_pct": round(float((s[up] > 0).mean()) * 100, 1),
            },
            "brent_baixa": {
                "n": int(dn.sum()),
                "media_pct": round(float(s[dn].mean()) * 100, 3),
                "mediana_pct": round(float(s[dn].median()) * 100, 3),
                "acerto_pct": round(float((s[dn] < 0).mean()) * 100, 1),
            },
            "brent_lateral": {
                "n": int(flat.sum()),
                "media_pct": round(float(s[flat].mean()) * 100, 3) if flat.sum() else None,
            },
        }
    return out


def rel_stats(rets: pd.DataFrame, window: int = 252) -> dict:
    sub = rets.iloc[-window:]
    out = {}
    for col in ["PRIO3", "PETR3", "CVX"]:
        x = sub["BRENT"]; y = sub[col]
        corr = float(np.corrcoef(x, y)[0, 1])
        beta = float(np.cov(y, x)[0, 1] / np.var(x))
        out[col] = {"corr": round(corr, 3), "beta": round(beta, 3), "n": len(sub)}
    return out


def indexed_series(prices: pd.DataFrame, months: int = 60) -> list:
    """Serie mensal indexada base 100 (ultimos N meses)."""
    m = prices.resample("ME").last().dropna()
    if len(m) > months:
        m = m.iloc[-months:]
    base = m.iloc[0]
    idx = (m / base * 100).round(2)
    rows = []
    for dt, row in idx.iterrows():
        rows.append({
            "mes": dt.strftime("%Y-%m"),
            "PRIO3": float(row["PRIO3"]),
            "PETR3": float(row["PETR3"]),
            "CVX": float(row["CVX"]),
            "BRENT": float(row["BRENT"]),
        })
    return rows


def daily_recent(rets: pd.DataFrame, days: int = 90) -> list:
    sub = rets.iloc[-days:].copy()
    rows = []
    for dt, row in sub.iterrows():
        br = float(row["BRENT"])
        rows.append({
            "data": dt.strftime("%Y-%m-%d"),
            "brent_pct": round(br * 100, 2),
            "brent_dir": "alta" if br > 0.001 else ("baixa" if br < -0.001 else "flat"),
            "PRIO3_pct": round(float(row["PRIO3"]) * 100, 2),
            "PETR3_pct": round(float(row["PETR3"]) * 100, 2),
            "CVX_pct": round(float(row["CVX"]) * 100, 2),
        })
    return rows


def cumulative_brent_split(rets: pd.DataFrame) -> dict:
    """Soma simples dos retornos diarios em dias de alta vs baixa do Brent."""
    b = rets["BRENT"]
    out = {}
    for col in ["PRIO3", "PETR3", "CVX"]:
        s = rets[col]
        up = b > 0.001
        dn = b < -0.001
        soma_up = float(s[up].sum()) * 100
        soma_dn = float(s[dn].sum()) * 100
        out[col] = {
            "soma_dias_brent_alta_pct": round(soma_up, 1),
            "soma_dias_brent_baixa_pct": round(soma_dn, 1),
            "n_dias_alta": int(up.sum()),
            "n_dias_baixa": int(dn.sum()),
        }
    return out


def snapshot(prices: pd.DataFrame) -> dict:
    last = prices.iloc[-1]
    rets = prices.pct_change().dropna()
    ytd_start = prices[prices.index >= f"{prices.index[-1].year}-01-01"].iloc[0]
    out = {}
    for col in ["PRIO3", "PETR3", "CVX", "BRENT"]:
        s = prices[col]
        r1m = (s.iloc[-1] / s.iloc[-22] - 1) * 100 if len(s) > 22 else None
        ytd = (s.iloc[-1] / ytd_start[col] - 1) * 100
        tot = (s.iloc[-1] / s.iloc[0] - 1) * 100
        out[col] = {
            "preco": round(float(last[col]), 2),
            "ret_1m_pct": round(float(r1m), 1) if r1m is not None else None,
            "ret_ytd_pct": round(float(ytd), 1),
            "ret_total_pct": round(float(tot), 1),
            "vol_anual_pct": round(float(rets[col].std() * np.sqrt(252) * 100), 1),
        }
    return out


def main() -> None:
    prices = fetch_all()
    prices.to_csv(ROOT / "raw_oil_peers.csv")
    rets = prices.pct_change().dropna()

    out = {
        "fonte": "Yahoo Finance (PRIO3.SA, PETR3.SA, CVX, BZ=F)",
        "periodo": {"inicio": prices.index[0].strftime("%Y-%m-%d"),
                    "fim": prices.index[-1].strftime("%Y-%m-%d"),
                    "pregoes": len(prices)},
        "labels": LABELS,
        "snapshot": snapshot(prices),
        "relativo_252d": rel_stats(rets),
        "efeito_brent": brent_effect(rets),
        "acumulado_por_direcao_brent": cumulative_brent_split(rets),
        "indexado_mensal": indexed_series(prices),
        "diario_90d": daily_recent(rets),
    }

    # leitura automatica
    eff = out["efeito_brent"]
    best_up = max(["PRIO3", "PETR3", "CVX"], key=lambda k: eff[k]["brent_alta"]["media_pct"])
    best_dn = min(["PRIO3", "PETR3", "CVX"], key=lambda k: eff[k]["brent_baixa"]["media_pct"])
    out["leitura"] = (
        f"Nos dias em que o Brent sobe, {LABELS[best_up]} reage com maior media (+{eff[best_up]['brent_alta']['media_pct']}%). "
        f"Nos dias de queda do Brent, {LABELS[best_dn]} cai menos (media {eff[best_dn]['brent_baixa']['media_pct']}%). "
        f"Beta 252d: PRIO3 {out['relativo_252d']['PRIO3']['beta']}, Petrobras {out['relativo_252d']['PETR3']['beta']}, "
        f"Chevron {out['relativo_252d']['CVX']['beta']}."
    )

    (ROOT / "oil_peers_compare.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps({"snapshot": out["snapshot"], "efeito_brent": out["efeito_brent"],
                      "relativo": out["relativo_252d"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
