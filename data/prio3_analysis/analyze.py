"""Consolida precos + fatos relevantes em um dataset de analise (analysis.json)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent


def rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return float((100 - 100 / (1 + rs)).iloc[-1])


def main() -> None:
    m = pd.read_csv(OUT / "merged_close.csv", parse_dates=["Date"]).set_index("Date")
    m = m.sort_index()
    prio = m["PRIO3"].dropna()
    brent = m["BRENT"].dropna()

    stats = json.loads((OUT / "stats_prices.json").read_text())

    # Retornos anuais (ano-calendario)
    def annual(s: pd.Series) -> dict:
        yr = s.groupby(s.index.year)
        out = {}
        for y, grp in yr:
            out[str(y)] = round((grp.iloc[-1] / grp.iloc[0] - 1) * 100, 1)
        return out

    annual_prio = annual(prio)
    annual_brent = annual(brent)

    # Serie mensal normalizada base 100 (fim de mes)
    mm = m[["PRIO3", "BRENT"]].dropna().resample("ME").last().dropna()
    base_p, base_b = mm["PRIO3"].iloc[0], mm["BRENT"].iloc[0]
    monthly = [
        {
            "date": d.strftime("%Y-%m"),
            "prio3": round(float(r["PRIO3"]), 2),
            "brent": round(float(r["BRENT"]), 2),
            "prio3_idx": round(float(r["PRIO3"] / base_p * 100), 1),
            "brent_idx": round(float(r["BRENT"] / base_b * 100), 1),
        }
        for d, r in mm.iterrows()
    ]

    # Tecnicos PRIO3
    last = float(prio.iloc[-1])
    sma50 = float(prio.rolling(50).mean().iloc[-1])
    sma200 = float(prio.rolling(200).mean().iloc[-1])
    hi52 = float(prio.iloc[-252:].max())
    lo52 = float(prio.iloc[-252:].min())
    running_max = prio.cummax()
    dd = (prio / running_max - 1) * 100
    cur_dd = float(dd.iloc[-1])
    max_dd = float(dd.min())
    max_dd_date = str(dd.idxmin().date())

    technicals = {
        "preco_atual": round(last, 2),
        "sma50": round(sma50, 2),
        "sma200": round(sma200, 2),
        "acima_sma50": last > sma50,
        "acima_sma200": last > sma200,
        "rsi14": round(rsi(prio), 1),
        "maxima_52s": round(hi52, 2),
        "minima_52s": round(lo52, 2),
        "dist_maxima_52s_pct": round((last / hi52 - 1) * 100, 1),
        "drawdown_atual_pct": round(cur_dd, 1),
        "max_drawdown_pct": round(max_dd, 1),
        "max_drawdown_data": max_dd_date,
    }

    # Correlacao movel 90d (amostrada mensal)
    joint = m[["PRIO3", "BRENT"]].dropna().pct_change()
    rc = joint["PRIO3"].rolling(90).corr(joint["BRENT"])
    rc_m = rc.resample("ME").last().dropna()
    rolling_corr = [
        {"date": d.strftime("%Y-%m"), "corr": round(float(v), 2)}
        for d, v in rc_m.items()
    ]

    # Fatos relevantes
    fatos = pd.read_csv(OUT / "fatos_relevantes_prio.csv")
    date_col = "Data_Referencia" if "Data_Referencia" in fatos.columns else fatos.columns[-1]
    subj_col = next(c for c in fatos.columns if c.lower() == "assunto")
    fatos = fatos.dropna(subset=[subj_col])
    fatos_by_year = fatos.assign(_y=fatos[date_col].astype(str).str[:4]).groupby("_y").size().to_dict()

    # Curadoria de catalisadores relevantes (por palavra-chave)
    def tag(subj: str) -> str | None:
        s = subj.lower()
        if any(k in s for k in ["início de produção", "start-up", "start up", "produção do", "retomada"]):
            return "Produção"
        if any(k in s for k in ["aquisição", "conclusão da aquisição", "conclusão de aquisição", "participação no campo"]):
            return "M&A / Aquisição"
        if any(k in s for k in ["certificação de reserva"]):
            return "Reservas"
        if any(k in s for k in ["debênture", "notas representativa", "emissão de notas", "follow-on", "oferta pública"]):
            return "Financiamento"
        if any(k in s for k in ["recompra", "dividendo", "cancelamento de ações", "desdobramento", "aumento de capital"]):
            return "Retorno ao acionista"
        if any(k in s for k in ["licença", "ibama", "anuência"]):
            return "Licenciamento"
        return None

    fatos["_tag"] = fatos[subj_col].map(tag)
    curated = (
        fatos[fatos["_tag"].notna()][[date_col, subj_col, "_tag"]]
        .rename(columns={date_col: "date", subj_col: "assunto", "_tag": "tag"})
        .to_dict("records")
    )
    tag_counts = fatos["_tag"].value_counts().to_dict()

    analysis = {
        "gerado_em": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "snapshot": {
            "prio3_brl": round(last, 2),
            "brent_usd": round(float(brent.iloc[-1]), 2),
            "usdbrl": round(float(m["USDBRL"].dropna().iloc[-1]), 2),
            "data": str(prio.index[-1].date()),
        },
        "stats5y": stats,
        "annual_returns": {"PRIO3": annual_prio, "BRENT": annual_brent},
        "monthly": monthly,
        "technicals": technicals,
        "rolling_corr": rolling_corr,
        "fatos_total": int(len(fatos)),
        "fatos_by_year": fatos_by_year,
        "fatos_tag_counts": {k: int(v) for k, v in tag_counts.items()},
        "catalisadores": curated,
    }

    (OUT / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
    print("OK analysis.json")
    print("Snapshot:", json.dumps(analysis["snapshot"], ensure_ascii=False))
    print("Technicals:", json.dumps(technicals, ensure_ascii=False))
    print("Annual PRIO3:", annual_prio)
    print("Annual BRENT:", annual_brent)
    print("Tag counts:", tag_counts)
    print("Catalisadores:", len(curated))


if __name__ == "__main__":
    main()
