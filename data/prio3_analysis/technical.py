"""Analise tecnica completa de PRIO3 a partir dos dados OHLCV diarios."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def main() -> None:
    df = pd.read_csv(OUT / "raw_PRIO3.csv", parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    price = float(c.iloc[-1])

    # Medias
    sma = {n: float(c.rolling(n).mean().iloc[-1]) for n in (9, 20, 50, 100, 200)}
    ema21 = float(ema(c, 21).iloc[-1])
    ema9 = float(ema(c, 9).iloc[-1])

    # MACD (12,26,9)
    macd_line = ema(c, 12) - ema(c, 26)
    signal = ema(macd_line, 9)
    hist = macd_line - signal
    macd = {
        "macd": round(float(macd_line.iloc[-1]), 3),
        "signal": round(float(signal.iloc[-1]), 3),
        "hist": round(float(hist.iloc[-1]), 3),
        "cruzamento": "alta" if macd_line.iloc[-1] > signal.iloc[-1] else "baixa",
    }

    # RSI
    rsi14 = float(rsi(c).iloc[-1])

    # Bollinger (20, 2 desvios)
    mid = c.rolling(20).mean()
    std = c.rolling(20).std()
    bb_up = float((mid + 2 * std).iloc[-1])
    bb_dn = float((mid - 2 * std).iloc[-1])
    bb_pctb = float((price - bb_dn) / (bb_up - bb_dn) * 100)

    # ATR(14) - volatilidade
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])
    atr_pct = atr / price * 100

    # 52 semanas
    last252 = c.iloc[-252:]
    hi52, lo52 = float(last252.max()), float(last252.min())

    # Suportes/Resistencias via swing highs/lows (janela 10) nos ultimos 12 meses
    win = 10
    recent = df.iloc[-252:].reset_index(drop=True)
    highs, lows = [], []
    for i in range(win, len(recent) - win):
        seg_h = recent["High"].iloc[i - win:i + win + 1]
        seg_l = recent["Low"].iloc[i - win:i + win + 1]
        if recent["High"].iloc[i] == seg_h.max():
            highs.append(float(recent["High"].iloc[i]))
        if recent["Low"].iloc[i] == seg_l.min():
            lows.append(float(recent["Low"].iloc[i]))

    def cluster(levels: list[float], tol: float = 0.02) -> list[float]:
        levels = sorted(levels)
        out: list[list[float]] = []
        for x in levels:
            if out and abs(x - out[-1][-1]) / out[-1][-1] <= tol:
                out[-1].append(x)
            else:
                out.append([x])
        return [round(float(np.mean(g)), 2) for g in out]

    res = [x for x in cluster(highs) if x > price][:3]
    sup = [x for x in cluster(lows) if x < price][-3:][::-1]

    # Fibonacci do movimento 2026 (minimo dez/2025 -> maximo mar/2026)
    swing_low = float(df[df["Date"] >= "2025-12-01"]["Low"].min())
    swing_high = float(df[df["Date"] >= "2025-12-01"]["High"].max())
    rng = swing_high - swing_low
    fib = {
        "0.0 (topo)": round(swing_high, 2),
        "23.6%": round(swing_high - 0.236 * rng, 2),
        "38.2%": round(swing_high - 0.382 * rng, 2),
        "50.0%": round(swing_high - 0.5 * rng, 2),
        "61.8%": round(swing_high - 0.618 * rng, 2),
        "100.0 (base)": round(swing_low, 2),
    }

    # Volume
    vol_med20 = float(v.rolling(20).mean().iloc[-1])
    vol_med90 = float(v.rolling(90).mean().iloc[-1])

    # Tendencia (alinhamento de medias)
    up_stack = price > sma[50] > sma[200]
    trend = "Alta" if price > sma[200] and sma[50] > sma[200] else ("Baixa" if price < sma[200] and sma[50] < sma[200] else "Lateral/Transicao")

    # Sinais consolidados
    sinais = []
    sinais.append(("Tendencia primaria (MM200)", "Positiva" if price > sma[200] else "Negativa"))
    sinais.append(("Tendencia media (MM50)", "Positiva" if price > sma[50] else "Negativa"))
    sinais.append(("MACD (12/26/9)", "Compra" if macd["cruzamento"] == "alta" else "Venda"))
    sinais.append(("RSI(14)", "Sobrecomprado" if rsi14 > 70 else ("Sobrevendido" if rsi14 < 30 else "Neutro")))
    sinais.append(("Bandas de Bollinger (%B)", "Topo" if bb_pctb > 80 else ("Fundo" if bb_pctb < 20 else "Meio")))
    sinais.append(("Golden/Death cross", "Golden (MM50>MM200)" if sma[50] > sma[200] else "Death (MM50<MM200)"))

    ta = {
        "data": str(df["Date"].iloc[-1].date()),
        "preco": round(price, 2),
        "tendencia": trend,
        "medias": {f"SMA{n}": round(sma[n], 2) for n in sma} | {"EMA9": round(ema9, 2), "EMA21": round(ema21, 2)},
        "acima_de": {f"SMA{n}": bool(price > sma[n]) for n in sma},
        "macd": macd,
        "rsi14": round(rsi14, 1),
        "bollinger": {"superior": round(bb_up, 2), "inferior": round(bb_dn, 2), "pctB": round(bb_pctb, 1)},
        "atr14": round(atr, 2), "atr_pct": round(atr_pct, 2),
        "range_52s": {"maxima": round(hi52, 2), "minima": round(lo52, 2),
                       "pos_pct": round((price - lo52) / (hi52 - lo52) * 100, 1)},
        "suportes": sup, "resistencias": res,
        "fibonacci_2026": fib,
        "volume": {"medio_20d": int(vol_med20), "medio_90d": int(vol_med90),
                    "tendencia_volume": "acima" if vol_med20 > vol_med90 else "abaixo"},
        "golden_cross": bool(sma[50] > sma[200]),
        "sinais": sinais,
    }

    (OUT / "technical.json").write_text(json.dumps(ta, indent=2, ensure_ascii=False))
    print(json.dumps(ta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
