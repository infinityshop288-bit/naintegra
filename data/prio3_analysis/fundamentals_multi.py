"""Analise FUNDAMENTALISTA de todo o universo -> fundamentals_multi.json.

Por acao:
  - multiplos e indicadores (P/L, P/VP, EV/EBITDA, DY, ROE, margens, Div/PL, cresc.);
  - DEMONSTRACAO FINANCEIRA trimestral dos ultimos ~2 anos (receita, lucro, EBITDA,
    margens) com variacao ano-a-ano do trimestre mais recente;
  - PLACAR fundamentalista (-100..+100) combinando valor, qualidade, crescimento e
    saude financeira, com tag (Forte / Solida / Neutra / Atencao / Fragil) e leitura.

Fonte: Yahoo Finance (info + quarterly_income_stmt). Bancos/seguradoras nao expoem
EBITDA/margem bruta: o placar se apoia em ROE, margem liquida, P/L, P/VP e dividendos.
"""
from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

from universe import UNIVERSE, yahoo_symbol  # noqa: E402

ROOT = Path(__file__).resolve().parent
FIN_SETORES = {"Bancos", "Seguradora"}


def clip(x, lo=-100.0, hi=100.0):
    return max(lo, min(hi, x))


def _row(df, names):
    for n in names:
        if n in df.index:
            s = df.loc[n]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[0]
            return s
    return None


def _num(x):
    try:
        f = float(x)
        return f if f == f else None
    except Exception:  # noqa: BLE001
        return None


def quarters(tk, moeda_div=1e9):
    """Ultimos ~8 trimestres da DRE (mais antigo -> mais recente)."""
    try:
        q = tk.quarterly_income_stmt
    except Exception:  # noqa: BLE001
        return []
    if q is None or q.empty:
        return []
    cols = list(q.columns)[:8]
    rev = _row(q, ["Total Revenue", "Operating Revenue"])
    ni = _row(q, ["Net Income", "Net Income Common Stockholders",
                  "Net Income Including Noncontrolling Interests",
                  "Net Income From Continuing Operation Net Minority Interest"])
    eb = _row(q, ["EBITDA", "Normalized EBITDA"])
    out = []
    for c in cols:
        r = _num(rev.get(c)) if rev is not None else None
        n = _num(ni.get(c)) if ni is not None else None
        e = _num(eb.get(c)) if eb is not None else None
        out.append({
            "periodo": f"{c.year}T{ (c.month - 1)//3 + 1 }",
            "data": str(c.date()),
            "receita": round(r / moeda_div, 3) if r is not None else None,
            "lucro": round(n / moeda_div, 3) if n is not None else None,
            "ebitda": round(e / moeda_div, 3) if e is not None else None,
            "margem_liq": round(n / r * 100, 1) if (r and n is not None and r != 0) else None,
            "margem_ebitda": round(e / r * 100, 1) if (r and e is not None and r != 0) else None,
        })
    out.reverse()  # cronologico
    return out


def yoy(qs):
    """Variacao ano-a-ano (mesmo trimestre) do periodo mais recente."""
    if len(qs) < 5:
        return {"receita_pct": None, "lucro_pct": None, "base": None}
    cur = qs[-1]; base = qs[-5]
    def pc(a, b):
        if a is None or b is None or b == 0:
            return None
        return round((a / b - 1) * 100, 1)
    return {"receita_pct": pc(cur["receita"], base["receita"]),
            "lucro_pct": pc(cur["lucro"], base["lucro"]), "base": base["periodo"]}


def ttm(qs):
    """Soma dos ultimos 4 trimestres (12 meses)."""
    last4 = [q for q in qs[-4:]]
    if len(last4) < 4:
        return {"receita": None, "lucro": None, "margem_liq": None}
    rev = sum(q["receita"] for q in last4 if q["receita"] is not None) if all(q["receita"] is not None for q in last4) else None
    ni = sum(q["lucro"] for q in last4 if q["lucro"] is not None) if all(q["lucro"] is not None for q in last4) else None
    return {"receita": round(rev, 3) if rev is not None else None,
            "lucro": round(ni, 3) if ni is not None else None,
            "margem_liq": round(ni / rev * 100, 1) if (rev and ni is not None) else None}


def score(ind, is_fin):
    """Placar fundamentalista -100..+100 (valor + qualidade + crescimento + saude)."""
    def av(parts):
        parts = [(w, v) for w, v in parts if v is not None]
        wsum = sum(w for w, _ in parts)
        return (sum(w * v for w, v in parts) / wsum) if wsum else None

    pe, pb, eveb = ind.get("pl"), ind.get("pvp"), ind.get("ev_ebitda")
    dy, roe, nm = ind.get("dy"), ind.get("roe"), ind.get("margem_liq")
    rg, eg = ind.get("cresc_receita"), ind.get("cresc_lucro")
    de = ind.get("div_pl")

    valor = av([
        (0.40, clip((14 - pe) * 8) if (pe and pe > 0) else None),
        (0.30, clip((2.2 - pb) * 45) if (pb and pb > 0) else None),
        (0.20, clip((8 - eveb) * 12) if (eveb and eveb > 0 and not is_fin) else None),
        (0.10, clip((dy or 0) * 8) if dy is not None else None),
    ])
    qualidade = av([
        (0.55, clip((roe - 12) * 5) if roe is not None else None),
        (0.45, clip((nm - 10) * 3) if nm is not None else None),
    ])
    cresc = av([
        (0.55, clip((rg or 0) * 4) if rg is not None else None),
        (0.45, clip((eg or 0) * 3) if eg is not None else None),
    ])
    saude = None
    if not is_fin and de is not None:
        saude = clip((1.0 - de / 100.0) * 70)

    comp = [(0.30, valor), (0.35, qualidade), (0.20, cresc)]
    if saude is not None:
        comp.append((0.15, saude))
    comp = [(w, v) for w, v in comp if v is not None]
    wsum = sum(w for w, _ in comp) or 1
    sc = round(clip(sum(w * v for w, v in comp) / wsum))
    if sc >= 45:
        tag = "FORTE"
    elif sc >= 15:
        tag = "SÓLIDA"
    elif sc > -15:
        tag = "NEUTRA"
    elif sc > -45:
        tag = "ATENÇÃO"
    else:
        tag = "FRÁGIL"
    return sc, tag, {"valor": None if valor is None else round(valor),
                     "qualidade": None if qualidade is None else round(qualidade),
                     "crescimento": None if cresc is None else round(cresc),
                     "saude": None if saude is None else round(saude)}


def leitura(ind, tag, yy, is_fin):
    bits = []
    if ind.get("pl"):
        bits.append(f"P/L {ind['pl']:.1f}")
    if ind.get("pvp"):
        bits.append(f"P/VP {ind['pvp']:.1f}")
    if ind.get("roe") is not None:
        bits.append(f"ROE {ind['roe']:.0f}%")
    if ind.get("margem_liq") is not None:
        bits.append(f"margem líq. {ind['margem_liq']:.0f}%")
    if not is_fin and ind.get("div_pl") is not None:
        bits.append(f"dív/PL {ind['div_pl']/100:.1f}x")
    if ind.get("dy"):
        bits.append(f"DY {ind['dy']:.1f}%")
    head = {"FORTE": "Fundamentos fortes", "SÓLIDA": "Fundamentos sólidos",
            "NEUTRA": "Fundamentos neutros", "ATENÇÃO": "Fundamentos exigem atenção",
            "FRÁGIL": "Fundamentos frágeis"}[tag]
    tail = ""
    if yy.get("receita_pct") is not None or yy.get("lucro_pct") is not None:
        r = yy.get("receita_pct"); l = yy.get("lucro_pct")
        tail = (f" Último tri vs 1 ano: receita {r:+.0f}%" if r is not None else "")
        tail += (f", lucro {l:+.0f}%" if l is not None else "")
        tail += " a/a." if tail else ""
    return f"{head} — " + ", ".join(bits) + "." + tail


def main() -> None:
    empresas = {}
    for t, (nome, setor, root) in UNIVERSE.items():
        sym = yahoo_symbol(t)
        info = {}
        for _ in range(2):
            try:
                info = yf.Ticker(sym).info or {}
                if info:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(1.0)
        tk = yf.Ticker(sym)
        is_fin = setor in FIN_SETORES
        moeda = info.get("financialCurrency") or "BRL"

        def g(k):
            return _num(info.get(k))
        ind = {
            "pl": g("trailingPE"), "pl_proj": g("forwardPE"), "pvp": g("priceToBook"),
            "psr": g("priceToSalesTrailing12Months"), "ev_ebitda": g("enterpriseToEbitda"),
            "dy": (g("dividendYield")), "roe": (g("returnOnEquity") or 0) * 100 if g("returnOnEquity") is not None else None,
            "margem_liq": (g("profitMargins") * 100) if g("profitMargins") is not None else None,
            "margem_bruta": (g("grossMargins") * 100) if g("grossMargins") else None,
            "margem_ebitda": (g("ebitdaMargins") * 100) if g("ebitdaMargins") else None,
            "div_pl": g("debtToEquity"),
            "cresc_receita": (g("revenueGrowth") * 100) if g("revenueGrowth") is not None else None,
            "cresc_lucro": (g("earningsGrowth") * 100) if g("earningsGrowth") is not None else None,
            "liq_corrente": g("currentRatio"),
            "market_cap": g("marketCap"), "vpa": g("bookValue"),
        }
        div = 1e9
        qs = quarters(tk, div)
        yy = yoy(qs)
        tt = ttm(qs)
        sc, tag, comp = score(ind, is_fin)
        txt = leitura(ind, tag, yy, is_fin)
        empresas[t] = {
            "nome": nome, "setor": setor, "moeda": moeda, "is_financeira": is_fin,
            "indicadores": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in ind.items()},
            "score": sc, "tag": tag, "componentes": comp, "leitura": txt,
            "yoy": yy, "ttm": tt, "trimestres": qs,
        }
        print(f"{t:<7}{setor:<18}{tag:<9} score {sc:>4} | "
              f"P/L {ind['pl'] if ind['pl'] else '-'} ROE {round(ind['roe']) if ind['roe'] is not None else '-'}% "
              f"| tri {len(qs)} | YoY rec {yy['receita_pct']} luc {yy['lucro_pct']}")

    out = {"atualizado": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
           "fonte": "Yahoo Finance (info + DRE trimestral)", "empresas": empresas}
    (ROOT / "fundamentals_multi.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print("\nsalvo fundamentals_multi.json |", len(empresas), "empresas")


if __name__ == "__main__":
    main()
