"""Estudo de padroes -> gatilhos de investimento em PRIO3.

Para cada sinal (evento no fechamento do dia t), mede o retorno FUTURO do
fechamento[t] ao fechamento[t+h] para h em {1,3,5,10,21} pregoes, e compara
com o baseline (todos os dias). Reporta n, retorno medio, taxa de acerto e
t-stat aproximado. Fonte de precos: Yahoo Finance (raw_PRIO3.csv, raw_BRENT.csv).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
HORIZONS = [1, 3, 5, 10, 21]


def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1 + up/dn)


def load():
    p = pd.read_csv(OUT/"raw_PRIO3.csv", parse_dates=["Date"]).sort_values("Date").set_index("Date")
    b = pd.read_csv(OUT/"raw_BRENT.csv", parse_dates=["Date"]).sort_values("Date").set_index("Date")
    df = pd.DataFrame({"Close": p["Close"], "Open": p["Open"], "High": p["High"],
                       "Low": p["Low"], "Vol": p["Volume"], "Brent": b["Close"]})
    df["Brent"] = df["Brent"].ffill()
    df = df.dropna(subset=["Close"])
    c = df["Close"]
    df["ret1"] = c.pct_change()
    df["rsi"] = rsi(c)
    df["sma20"] = c.rolling(20).mean()
    df["sma50"] = c.rolling(50).mean()
    df["sma100"] = c.rolling(100).mean()
    df["sma200"] = c.rolling(200).mean()
    df["bb_mid"] = c.rolling(20).mean()
    df["bb_std"] = c.rolling(20).std()
    df["bb_up"] = df["bb_mid"] + 2*df["bb_std"]
    df["bb_dn"] = df["bb_mid"] - 2*df["bb_std"]
    df["macd"] = ema(c, 12) - ema(c, 26)
    df["macd_sig"] = ema(df["macd"], 9)
    df["ret5"] = c.pct_change(5)
    df["ret20"] = c.pct_change(20)
    df["brent_ret20"] = df["Brent"].pct_change(20)
    df["gap"] = df["Open"]/c.shift(1) - 1
    df["hi20"] = c.rolling(20).max()
    df["lo20"] = c.rolling(20).min()
    df["hi252"] = c.rolling(252).max()
    df["dist200"] = c/df["sma200"] - 1
    df["dow"] = df.index.weekday
    df["down3"] = (df["ret1"] < 0) & (df["ret1"].shift(1) < 0) & (df["ret1"].shift(2) < 0)
    # forward returns
    for h in HORIZONS:
        df[f"fwd{h}"] = c.shift(-h)/c - 1
    return df


def signals(df: pd.DataFrame) -> dict:
    c = df["Close"]
    cross_up = lambda a, b: (a > b) & (a.shift(1) <= b.shift(1))
    return {
        "RSI < 30 (sobrevendido)": df["rsi"] < 30,
        "RSI < 25 (muito sobrevendido)": df["rsi"] < 25,
        "RSI > 70 (sobrecomprado)": df["rsi"] > 70,
        "Pullback em tendencia (>MM200 e RSI<40)": (c > df["sma200"]) & (df["rsi"] < 40),
        "Preco abaixo da Banda inferior (2σ)": c < df["bb_dn"],
        "Preco acima da Banda superior (2σ)": c > df["bb_up"],
        "MACD cruza p/ cima do sinal": cross_up(df["macd"], df["macd_sig"]),
        "Golden cross (MM50 x MM200)": cross_up(df["sma50"], df["sma200"]),
        "Cruza acima da MM50": cross_up(c, df["sma50"]),
        "Cruza acima da MM200": cross_up(c, df["sma200"]),
        "Queda >=8% em 5 pregoes": df["ret5"] <= -0.08,
        "Queda >=12% em 5 pregoes": df["ret5"] <= -0.12,
        "3 quedas seguidas": df["down3"],
        "Nova maxima de 20 dias (rompimento)": c >= df["hi20"],
        "Novo fundo de 20 dias": c <= df["lo20"],
        "Rompe maxima de 52 semanas": c >= df["hi252"],
        ">20% abaixo da MM200 (deep value)": df["dist200"] <= -0.20,
        "Gap de baixa < -2%": df["gap"] < -0.02,
        "Gap de alta > +2%": df["gap"] > 0.02,
        "PRIO 20d - Brent 20d < -10pp (atraso)": (df["ret20"] - df["brent_ret20"]) < -0.10,
        "PRIO 20d - Brent 20d > +10pp (esticado)": (df["ret20"] - df["brent_ret20"]) > 0.10,
        "Segunda-feira": df["dow"] == 0,
        "Sexta-feira": df["dow"] == 4,
    }


def summarize(df, mask, h):
    col = f"fwd{h}"
    sub = df.loc[mask, col].dropna()
    base = df[col].dropna()
    n = len(sub)
    if n == 0:
        return None
    mean = sub.mean()
    hit = (sub > 0).mean()
    std = sub.std(ddof=1) if n > 1 else np.nan
    tstat = (mean - base.mean())/(std/np.sqrt(n)) if (std and std > 0) else np.nan
    return {"n": int(n), "media_pct": round(mean*100, 2), "acerto_pct": round(hit*100, 1),
            "vs_base_pp": round((mean - base.mean())*100, 2),
            "vs_base_acerto_pp": round((hit - (base > 0).mean())*100, 1),
            "tstat": round(float(tstat), 2) if tstat == tstat else None}


def main():
    df = load()
    base = {h: {"media_pct": round(df[f"fwd{h}"].mean()*100, 2),
                "acerto_pct": round((df[f"fwd{h}"] > 0).mean()*100, 1)} for h in HORIZONS}
    print("Baseline (qualquer dia):")
    for h in HORIZONS:
        print(f"  fwd{h}: media {base[h]['media_pct']}% | acerto {base[h]['acerto_pct']}%")

    sigs = signals(df)
    results = {}
    for name, mask in sigs.items():
        mask = mask.fillna(False)
        results[name] = {"n": int(mask.sum()),
                          "por_horizonte": {h: summarize(df, mask, h) for h in HORIZONS}}

    # Ranking por edge no horizonte de 10 pregoes (n>=15)
    rank = []
    for name, r in results.items():
        s10 = r["por_horizonte"].get(10)
        if s10 and r["n"] >= 15:
            rank.append((name, s10["n"], s10["media_pct"], s10["acerto_pct"], s10["vs_base_pp"], s10["tstat"]))
    rank.sort(key=lambda x: x[4], reverse=True)

    print("\n=== RANKING por vantagem no retorno de 10 pregoes (n>=15) ===")
    print(f"{'Sinal':<45}{'n':>4}{'med10%':>9}{'acerto%':>9}{'vs base':>9}{'t':>6}")
    for name, n, m, a, v, t in rank:
        print(f"{name:<45}{n:>4}{m:>9}{a:>9}{v:>9}{str(t):>6}")

    out = {"baseline": base, "resultados": results,
           "ranking_10d": [{"sinal": n, "n": nn, "media10_pct": m, "acerto_pct": a,
                             "vs_base_pp": v, "tstat": t} for n, nn, m, a, v, t in rank]}
    (OUT/"triggers.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print("\nOK triggers.json")


if __name__ == "__main__":
    main()
