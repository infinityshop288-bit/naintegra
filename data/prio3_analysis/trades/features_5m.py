#!/usr/bin/env python3
"""Extrai do caminho intradiario de 5 min aquilo que o candle diario esconde.

Por que nao e possivel analisar cada giro no candle de 5 min:
as notas da XP nao registram horario de execucao, so a data. O unico vinculo
com o relogio seria o preco do ativo reconstruido por Black-Scholes -- e medi:
o preco mediano de um giro e compativel com 10 barras de 5 min diferentes (19
com tolerancia), e ZERO dos 458 giros cai numa barra unica. Escolher uma barra
seria arbitrio disfarcado de medicao.

O que E possivel, e e util: medir PROPRIEDADES DO PREGAO a partir das barras de
5 min. Isso nao exige saber a hora do negocio, e se encaixa no nivel em que os
rotulos existem (o pregao). E ataca direto o achado da analise diaria -- que o
resultado depende de o dia ter dono ou estar disputado. A fracao do corpo no
candle diario e um proxy grosseiro disso; o caminho de 5 min mede de verdade.

A medida central e a razao de eficiencia (Kaufman): deslocamento liquido
dividido pela distancia total percorrida. Um dia que sobe 2% em linha reta tem
eficiencia perto de 1; um dia que sobe 2% depois de ziguezaguear 10% tem
eficiencia perto de 0,2. Os dois fecham com o mesmo candle diario.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
CACHE = AQUI / "market" / "prio3_5m.csv"
SAIDA = AQUI / "features_5m.json"


def carrega_barras() -> dict[str, pd.DataFrame]:
    b = pd.read_csv(CACHE, index_col=0, parse_dates=True)
    out: dict[str, pd.DataFrame] = {}
    for d, g in b.groupby(b.index.date):
        if len(g) >= 20:  # pregao truncado nao sustenta medida de caminho
            out[str(d)] = g.sort_index()
    return out


def features(g: pd.DataFrame) -> dict:
    c = g["Close"].to_numpy(dtype=float)
    h, l = g["High"].to_numpy(dtype=float), g["Low"].to_numpy(dtype=float)
    o = float(g["Open"].iloc[0])
    dif = np.diff(c)
    percorrido = float(np.abs(dif).sum())
    liquido = float(c[-1] - o)

    # razao de eficiencia: 1 = linha reta, 0 = ziguezague puro
    efic = abs(liquido) / percorrido if percorrido > 0 else 0.0

    # quantas vezes o movimento de 5 min trocou de sinal
    sinais = np.sign(dif)
    sinais = sinais[sinais != 0]
    reversoes = int((np.diff(sinais) != 0).sum()) if len(sinais) > 1 else 0

    n = len(c)
    i_max, i_min = int(np.argmax(h)), int(np.argmin(l))
    rng = float(h.max() - l.min())

    return {
        "barras": n,
        "eficiencia": round(efic, 4),
        "direcao": "alta" if liquido >= 0 else "baixa",
        "ret_dia": round(100 * liquido / o, 3) if o else None,
        "percorrido_pct": round(100 * percorrido / o, 3) if o else None,
        "reversoes": reversoes,
        "reversoes_por_barra": round(reversoes / max(1, n - 1), 4),
        # quando o extremo aconteceu, em fracao da sessao (0 = abertura)
        "hora_max": round(i_max / max(1, n - 1), 3),
        "hora_min": round(i_min / max(1, n - 1), 3),
        # a ultima hora confirmou ou desmentiu o dia?
        "ret_ultima_hora": round(100 * (c[-1] - c[max(0, n - 13)]) / c[max(0, n - 13)], 3),
        "vol_5m_anualizada": round(float(np.std(dif / c[:-1], ddof=1)) * (252 * n) ** 0.5 * 100, 2)
        if n > 2 else None,
        "fechou_na_barra": round((c[-1] - l.min()) / rng, 3) if rng > 0 else None,
    }


def main() -> int:
    barras = carrega_barras()
    feats = {d: features(g) for d, g in barras.items()}
    SAIDA.write_text(json.dumps(feats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{len(feats)} pregoes com caminho de 5 min\n")
    ef = sorted((v["eficiencia"], d) for d, v in feats.items())
    print("Dias mais ziguezagueados (eficiencia baixa = muita briga):")
    for e, d in ef[:5]:
        v = feats[d]
        print(f"  {d}  efic {e:.2f}  ret {v['ret_dia']:+6.2f}%  "
              f"percorreu {v['percorrido_pct']:5.2f}%  {v['reversoes']} reversoes")
    print("\nDias mais limpos (eficiencia alta = um lado mandou):")
    for e, d in ef[-5:]:
        v = feats[d]
        print(f"  {d}  efic {e:.2f}  ret {v['ret_dia']:+6.2f}%  "
              f"percorreu {v['percorrido_pct']:5.2f}%  {v['reversoes']} reversoes")
    print(f"\n[OK] {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
