"""Perfil intradiário de volume x direção da PRIO3.

Objetivo: achar os horários de MAIOR volume (melhores p/ operar SEGUINDO A ALTA)
e os de MENOR volume (para operar SEGUINDO A BAIXA), analisando:
  - volume médio por faixa de horário (30 min)
  - % do volume diário concentrado em cada faixa
  - retorno médio da faixa (viés direcional intradia)
  - volume em candles de ALTA vs candles de BAIXA por faixa
  - taxa de acerto de "seguir a direção" (momentum) por faixa

Fonte: Yahoo Finance (PRIO3.SA), candles de 15 min nos últimos 60 dias.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent
TZ = "America/Sao_Paulo"


def load_intraday(interval: str = "15m", period: str = "60d") -> pd.DataFrame:
    df = yf.download("PRIO3.SA", interval=interval, period=period,
                     auto_adjust=False, progress=False)
    if df.empty:
        raise SystemExit("sem dados intradiários")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    df.index = idx.tz_convert(TZ)
    # pregão B3: 10:00–17:00 (ignora leilão/after)
    df = df.between_time("10:00", "17:00").copy()
    df["date"] = df.index.date
    df["hhmm"] = df.index.strftime("%H:%M")
    df["ret"] = (df["Close"] / df["Open"] - 1.0)  # retorno da própria barra
    df["up"] = df["ret"] > 0
    return df.dropna(subset=["Volume", "ret"])


def by_bucket(df: pd.DataFrame) -> pd.DataFrame:
    # volume diário total p/ calcular participação de cada faixa
    day_vol = df.groupby("date")["Volume"].transform("sum")
    df = df.assign(part=df["Volume"] / day_vol)
    g = df.groupby("hhmm")
    out = pd.DataFrame({
        "vol_medio": g["Volume"].mean(),
        "part_pct": g["part"].mean() * 100,          # % médio do volume do dia
        "ret_medio_pct": g["ret"].mean() * 100,      # viés direcional da faixa
        "up_rate_pct": g["up"].mean() * 100,         # % de barras de alta
        "n": g["ret"].count(),
    })
    # volume só nas barras de alta vs baixa
    out["vol_alta"] = df[df["up"]].groupby("hhmm")["Volume"].mean()
    out["vol_baixa"] = df[~df["up"]].groupby("hhmm")["Volume"].mean()
    out["vol_alta_x_baixa"] = out["vol_alta"] / out["vol_baixa"]
    # momentum: barra seguinte segue a direção da atual?
    df2 = df.sort_index().copy()
    df2["ret_next"] = df2.groupby("date")["ret"].shift(-1)
    df2["cont"] = np.sign(df2["ret"]) == np.sign(df2["ret_next"])
    out["continua_pct"] = df2.groupby("hhmm")["cont"].mean() * 100
    return out.round(3)


def main() -> None:
    df = load_intraday()
    n_days = df["date"].nunique()
    tab = by_bucket(df)

    # ranking p/ ALTA: maior volume + viés/continuação positivos
    alta = tab.sort_values("vol_medio", ascending=False)
    # ranking p/ BAIXA: menor volume
    baixa = tab.sort_values("vol_medio", ascending=True)

    print(f"PRIO3 intradiário — {n_days} pregões, 15 min, fuso {TZ}\n")
    cols = ["vol_medio", "part_pct", "ret_medio_pct", "up_rate_pct", "vol_alta_x_baixa", "continua_pct", "n"]
    print("=== Por faixa de horário (ordem do dia) ===")
    print(tab[cols].to_string())

    print("\n=== MAIOR volume (seguir a ALTA) — top 6 ===")
    print(alta[cols].head(6).to_string())
    print("\n=== MENOR volume (seguir a BAIXA) — bottom 6 ===")
    print(baixa[cols].head(6).to_string())

    payload = {
        "fonte": "Yahoo Finance PRIO3.SA (15m, 60d)",
        "pregoes": int(n_days),
        "tz": TZ,
        "buckets": [
            {"hhmm": h, "vol_medio": float(r.vol_medio), "part_pct": float(r.part_pct),
             "ret_medio_pct": float(r.ret_medio_pct), "up_rate_pct": float(r.up_rate_pct),
             "vol_alta_x_baixa": None if pd.isna(r.vol_alta_x_baixa) else float(r.vol_alta_x_baixa),
             "continua_pct": None if pd.isna(r.continua_pct) else float(r.continua_pct)}
            for h, r in tab.iterrows()
        ],
        "top_volume_alta": list(alta.head(6).index),
        "menor_volume_baixa": list(baixa.head(6).index),
    }
    (OUT / "intraday_volume.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print("\nsalvo intraday_volume.json")


if __name__ == "__main__":
    main()
