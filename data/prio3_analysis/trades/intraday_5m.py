#!/usr/bin/env python3
"""Baixa e CACHEIA os candles de 5 minutos de PRIO3.

O Yahoo so serve intraday de 5 min dos ultimos 60 dias corridos. Isso tem duas
consequencias:

1. O historico de junho/inicio de julho ja nao existe mais em lugar nenhum de
   graca -- as operacoes de 16/06 a 09/07 ficam permanentemente sem barra de
   5 min.
2. O que ainda esta disponivel VAI sumir. Por isso este script faz merge com o
   cache em disco em vez de sobrescrever: rodando periodicamente, a cobertura
   so cresce.

Guardar isso agora e o que torna possivel qualquer analise intradiaria futura.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
CACHE = AQUI / "market" / "prio3_5m.csv"
TICKER = "PRIO3.SA"


def baixa() -> pd.DataFrame:
    import yfinance as yf

    d = yf.download(TICKER, period="60d", interval="5m",
                    progress=False, auto_adjust=False)
    if d is None or d.empty:
        return pd.DataFrame()
    if hasattr(d.columns, "nlevels") and d.columns.nlevels > 1:
        d.columns = d.columns.get_level_values(0)
    d = d[["Open", "High", "Low", "Close", "Volume"]].copy()
    d.index.name = "ts"
    return d


def main() -> int:
    novo = baixa()
    if novo.empty:
        print("[erro] download vazio", flush=True)
        return 1

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE.is_file():
        velho = pd.read_csv(CACHE, index_col=0, parse_dates=True)
        antes = len(velho)
        # o cache tem prioridade: barras antigas que o Yahoo ja nao serve mais
        # nao podem ser perdidas num merge
        juntos = pd.concat([velho, novo])
        juntos = juntos[~juntos.index.duplicated(keep="last")].sort_index()
    else:
        antes = 0
        juntos = novo.sort_index()

    juntos.to_csv(CACHE)
    dias = len(set(juntos.index.date))
    print(f"{len(juntos)} barras de 5 min ({len(juntos) - antes:+d}) | "
          f"{dias} pregoes | {juntos.index[0]} -> {juntos.index[-1]}", flush=True)
    print(f"[OK] {CACHE}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
