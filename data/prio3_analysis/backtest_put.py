"""Gatilhos de BAIXA para operar PUT em PRIO3.

Para cada sinal, mede o retorno futuro do ativo. Para PUT, interessa retorno
FUTURO NEGATIVO. Reporta n, retorno medio, % de quedas (taxa de acerto da PUT)
e t-stat. Ranqueia pelos sinais com retorno futuro mais negativo (melhores p/ PUT).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import backtest as bt

OUT = Path(__file__).resolve().parent
H = [1, 3, 5, 10, 21]


def bear_signals(df: pd.DataFrame) -> dict:
    c = df["Close"]
    cross_dn = lambda a, b: (a < b) & (a.shift(1) >= b.shift(1))
    up3 = (df["ret1"] > 0) & (df["ret1"].shift(1) > 0) & (df["ret1"].shift(2) > 0)
    dist200 = df["dist200"]
    relf = df["ret20"] - df["brent_ret20"]
    return {
        "Fecha ABAIXO da MM200 (perda de tendência)": cross_dn(c, df["sma200"]),
        "Fecha abaixo da MM50": cross_dn(c, df["sma50"]),
        "Death cross (MM50 x MM200)": cross_dn(df["sma50"], df["sma200"]),
        "MACD cruza p/ baixo do sinal": cross_dn(df["macd"], df["macd_sig"]),
        "Novo fundo de 20 dias (rompimento p/ baixo)": c <= df["lo20"],
        "Novo fundo de 52 semanas": c <= c.rolling(252).min(),
        "Abaixo da MM200 E MACD<sinal (baixa confirmada)": (c < df["sma200"]) & (df["macd"] < df["macd_sig"]),
        "RSI > 75 (topo — testar reversão)": df["rsi"] > 75,
        "Preço > Banda superior (2σ) — esticado": c > df["bb_up"],
        ">25% acima da MM200 (sobreesticado)": dist200 >= 0.25,
        "3 altas seguidas (exaustão curta)": up3,
        "PRIO 20d - Brent 20d < -10pp (fraqueza relativa)": relf < -0.10,
        "Queda >=8% em 5 pregões (continuação)": df["ret5"] <= -0.08,
        "Perde a MM200 estando abaixo por >=3 dias": (c < df["sma200"]) & (c.shift(3) < df["sma200"].shift(3)),
    }


def summarize(df, mask, h):
    col = f"fwd{h}"
    sub = df.loc[mask, col].dropna()
    base = df[col].dropna()
    n = len(sub)
    if n == 0:
        return None
    mean = sub.mean()
    neg = (sub < 0).mean()  # taxa de acerto p/ PUT (quedas)
    std = sub.std(ddof=1) if n > 1 else np.nan
    tstat = (mean - base.mean()) / (std / np.sqrt(n)) if (std and std > 0) else np.nan
    return {"n": int(n), "media_pct": round(mean * 100, 2), "queda_pct": round(neg * 100, 1),
            "vs_base_pp": round((mean - base.mean()) * 100, 2),
            "tstat": round(float(tstat), 2) if tstat == tstat else None}


def main():
    df = bt.load()
    base = {h: {"media_pct": round(df[f"fwd{h}"].mean() * 100, 2),
                "queda_pct": round((df[f"fwd{h}"] < 0).mean() * 100, 1)} for h in H}
    print("Baseline (qualquer dia) — % de quedas:")
    for h in H:
        print(f"  fwd{h}: media {base[h]['media_pct']}% | quedas {base[h]['queda_pct']}%")

    sigs = bear_signals(df)
    results = {}
    for name, mask in sigs.items():
        mask = mask.fillna(False)
        results[name] = {"n": int(mask.sum()), "por_horizonte": {h: summarize(df, mask, h) for h in H}}

    rank = []
    for name, r in results.items():
        s10 = r["por_horizonte"].get(10)
        if s10 and r["n"] >= 12:
            rank.append((name, s10["n"], s10["media_pct"], s10["queda_pct"], s10["vs_base_pp"], s10["tstat"]))
    rank.sort(key=lambda x: x[2])  # mais negativo primeiro

    print("\n=== RANKING p/ PUT — retorno de 10 pregões mais NEGATIVO (n>=12) ===")
    print(f"{'Sinal':<52}{'n':>4}{'med10%':>9}{'quedas%':>9}{'vsbase':>9}{'t':>7}")
    for name, n, m, q, v, t in rank:
        print(f"{name:<52}{n:>4}{m:>9}{q:>9}{v:>9}{str(t):>7}")

    out = {"baseline": base, "resultados": results,
           "ranking_put_10d": [{"sinal": n, "n": nn, "media10_pct": m, "queda_pct": q, "vs_base_pp": v, "tstat": t}
                                for n, nn, m, q, v, t in rank]}
    (OUT / "triggers_put.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))

    # status atual
    last = {name: bool(mask.fillna(False).iloc[-1]) for name, mask in sigs.items()}
    print("\nGatilhos de BAIXA ativos hoje:", [k for k, v in last.items() if v] or "nenhum")


if __name__ == "__main__":
    main()
