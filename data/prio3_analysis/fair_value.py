"""Calculo de preco justo de PRIO3: modelo EV/EBITDA + consenso de analistas."""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent

raw = json.loads((OUT / "valuation_raw.json").read_text())
yf = raw["yf"]

SHARES = yf["sharesOutstanding"] / 1e9          # bilhoes de acoes
PRICE = yf["currentPrice"]
NET_DEBT = raw["itr"]["divida_liquida"] / 1e6    # R$ mil -> R$ bilhoes
MKT_CAP = yf["marketCap"] / 1e9
EV = yf["enterpriseValue"] / 1e9

# EBITDA anualizado do 1T2026 (R$ mil -> bi) e cenarios normalizados
ebitda_1t = raw["itr"]["ebitda"] / 1e6
ebitda_scen = {"conservador": 13.0, "base": 16.0, "otimista": 18.0}
mults = [4.0, 4.5, 5.0, 5.5, 6.0]


def fair_by_multiple(ebitda: float, mult: float) -> float:
    ev = mult * ebitda
    equity = ev - NET_DEBT
    return equity / SHARES


grid = {}
for name, eb in ebitda_scen.items():
    grid[name] = {f"{m:.1f}x": round(fair_by_multiple(eb, m), 2) for m in mults}

central = fair_by_multiple(ebitda_scen["base"], 5.0)

consenso = {
    "n_analistas": yf["numberOfAnalystOpinions"],
    "recomendacao": yf["recommendationKey"],
    "alvo_medio": yf["targetMeanPrice"],
    "alvo_mediana": yf["targetMedianPrice"],
    "alvo_max": yf["targetHighPrice"],
    "alvo_min": yf["targetLowPrice"],
}

out = {
    "preco_atual": round(PRICE, 2),
    "acoes_bi": round(SHARES, 3),
    "market_cap_bi": round(MKT_CAP, 1),
    "ev_bi": round(EV, 1),
    "divida_liquida_bi": round(NET_DEBT, 1),
    "ev_ebitda_trailing": yf["enterpriseToEbitda"],
    "pe_trailing": round(yf["trailingPE"], 1),
    "pe_forward": round(yf["forwardPE"], 1),
    "p_vp": round(yf["priceToBook"], 2),
    "ebitda_1t26_anualizado_bi": round(ebitda_1t * 4, 1),
    "ebitda_cenarios_bi": ebitda_scen,
    "grid_preco_justo": grid,
    "preco_justo_central": round(central, 2),
    "upside_central_pct": round((central / PRICE - 1) * 100, 1),
    "consenso_analistas": consenso,
    "upside_consenso_pct": round((consenso["alvo_medio"] / PRICE - 1) * 100, 1),
}

(OUT / "fair_value.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
print(json.dumps(out, indent=2, ensure_ascii=False))
