"""Coleta macro em tempo (quase) real -> macro.json.

Fontes ABERTAS e reais:
  - BCB SGS (api.bcb.gov.br): Selic, IPCA, IGP-M, desemprego, inadimplencia, cambio
  - FRED (fred.stlouisfed.org, CSV sem chave): Fed Funds, desemprego EUA, US 10Y, CPI
  - Yahoo Finance: Ibovespa (^BVSP), DXY (DX-Y.NYB)
  - raw_BRENT.csv: direcao de commodities

Campos "curados" (sem API aberta em tempo real) vem marcados com fonte/mes.
"""
from __future__ import annotations

import csv
import io
import json
import ssl
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    CTX = ssl._create_unverified_context()

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"}


def _get(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "ignore")


def bcb(serie: int, n: int = 1):
    """Ultimos n valores de uma serie SGS do BCB."""
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/{n}?formato=json"
    data = json.loads(_get(url))
    return [(d["data"], float(d["valor"])) for d in data]


def bcb_last(serie: int):
    try:
        v = bcb(serie, 1)
        return v[-1] if v else (None, None)
    except Exception:  # noqa: BLE001
        return (None, None)


def bcb_acum12(serie: int):
    """Acumulado 12 meses de uma serie mensal (%)."""
    try:
        vals = [v for _, v in bcb(serie, 12)]
        if len(vals) < 12:
            return None
        acc = 1.0
        for v in vals:
            acc = acc * (1 + v / 100)  # noqa: F841
            acc_local = acc
        acc = 1.0
        for v in vals:
            acc *= (1 + v / 100)
        return round((acc - 1) * 100, 2)
    except Exception:  # noqa: BLE001
        return None


def _get_curl(url: str, timeout: int = 12, ua: str | None = None) -> str:
    """Fallback via curl. FRED quebra com UA de navegador (HTTP/2), entao UA=None."""
    import subprocess
    cmd = ["curl", "-s", "-m", str(timeout)]
    if ua:
        cmd += ["-A", ua]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout


def fred(series_id: str, tail: int = 14):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    txt = _get_curl(url)  # curl com UA padrao (FRED rejeita UA de navegador)
    try:
        rows = [r for r in csv.reader(io.StringIO(txt))][1:]
        rows = [(d, float(v)) for d, v in rows if v not in (".", "")]
        return rows[-tail:]
    except Exception:  # noqa: BLE001
        return []


def yf_series(sym: str):
    import yfinance as yf
    h = yf.download(sym, period="3mo", interval="1d", progress=False, auto_adjust=False)
    if isinstance(h.columns, pd.MultiIndex):
        h.columns = h.columns.get_level_values(0)
    return h["Close"].dropna()


def dir_of(s: pd.Series, lag: int = 21) -> int:
    if len(s) <= lag:
        return 0
    ch = s.iloc[-1] / s.iloc[-1 - lag] - 1
    return 1 if ch > 0.01 else (-1 if ch < -0.01 else 0)


def build_macro() -> dict:
    out = {"atualizado": date.today().isoformat(), "indicadores": {}, "direcoes": {}}
    I = out["indicadores"]

    # ---- BCB (oficial) ----
    d, v = bcb_last(432); I["selic_meta"] = {"valor": v, "unid": "% a.a.", "data": d, "fonte": "BCB", "tag": "oficial"}
    d, v = bcb_last(433); I["ipca_mes"] = {"valor": v, "unid": "% m", "data": d, "fonte": "BCB", "tag": "oficial"}
    I["ipca_12m"] = {"valor": bcb_acum12(433), "unid": "% 12m", "fonte": "BCB", "tag": "oficial"}
    d, v = bcb_last(189); I["igpm_mes"] = {"valor": v, "unid": "% m", "data": d, "fonte": "BCB", "tag": "oficial"}
    I["igpm_12m"] = {"valor": bcb_acum12(189), "unid": "% 12m", "fonte": "BCB", "tag": "oficial"}
    d, v = bcb_last(24369); I["desemprego_br"] = {"valor": v, "unid": "%", "data": d, "fonte": "BCB/PNAD", "tag": "oficial"}
    d, v = bcb_last(21082); I["inadimplencia_total"] = {"valor": v, "unid": "%", "data": d, "fonte": "BCB", "tag": "oficial"}
    d, v = bcb_last(21083); I["inadimplencia_pj"] = {"valor": v, "unid": "%", "data": d, "fonte": "BCB", "tag": "oficial"}
    d, v = bcb_last(21084); I["inadimplencia_pf"] = {"valor": v, "unid": "%", "data": d, "fonte": "BCB", "tag": "oficial"}
    try:
        cambio = bcb(1, 2)
    except Exception:  # noqa: BLE001
        cambio = []
    if cambio:
        d, v = cambio[-1]
        chg = (v / cambio[-2][1] - 1) * 100 if len(cambio) > 1 else None
        I["usd_brl"] = {"valor": round(v, 4), "chg_pct": round(chg, 2) if chg is not None else None,
                        "data": d, "fonte": "BCB", "tag": "oficial"}

    # ---- FRED (EUA) ----
    ff = fred("FEDFUNDS"); I["fed_funds"] = {"valor": ff[-1][1] if ff else None, "unid": "% a.a.", "data": ff[-1][0] if ff else None, "fonte": "FRED", "tag": "oficial"}
    ur = fred("UNRATE"); I["desemprego_us"] = {"valor": ur[-1][1] if ur else None, "unid": "%", "data": ur[-1][0] if ur else None, "fonte": "FRED", "tag": "oficial"}
    ty = fred("DGS10"); I["us_10y"] = {"valor": ty[-1][1] if ty else None, "unid": "%", "data": ty[-1][0] if ty else None, "fonte": "FRED", "tag": "oficial"}
    cpi = fred("CPIAUCSL", 14)
    if len(cpi) >= 13:
        yoy = (cpi[-1][1] / cpi[-13][1] - 1) * 100
        I["cpi_us_12m"] = {"valor": round(yoy, 2), "unid": "% 12m", "data": cpi[-1][0], "fonte": "FRED", "tag": "oficial"}

    # ---- Mercado (Yahoo) ----
    ibov_dir = usd_dir = commodity_dir = 0
    try:
        ib = yf_series("^BVSP")
        chg = (ib.iloc[-1] / ib.iloc[-2] - 1) * 100
        I["ibovespa"] = {"valor": round(float(ib.iloc[-1]), 0), "chg_pct": round(float(chg), 2),
                         "ret_1m_pct": round(float(ib.iloc[-1] / ib.iloc[-22] - 1) * 100, 1) if len(ib) > 22 else None,
                         "fonte": "Yahoo", "tag": "tempo real"}
        ibov_dir = dir_of(ib)
    except Exception:  # noqa: BLE001
        pass
    try:
        dxy = yf_series("DX-Y.NYB")
        I["dxy"] = {"valor": round(float(dxy.iloc[-1]), 2),
                    "chg_pct": round(float(dxy.iloc[-1] / dxy.iloc[-2] - 1) * 100, 2), "fonte": "Yahoo", "tag": "tempo real"}
    except Exception:  # noqa: BLE001
        pass
    # commodity direction via Brent (raw)
    try:
        br = pd.read_csv(ROOT / "raw_BRENT.csv")
        bc = pd.to_numeric(br["Close"], errors="coerce").dropna()
        commodity_dir = dir_of(bc)
    except Exception:  # noqa: BLE001
        pass
    if I.get("usd_brl", {}).get("chg_pct") is not None:
        usd_dir = 1 if I["usd_brl"]["chg_pct"] > 0 else (-1 if I["usd_brl"]["chg_pct"] < 0 else 0)

    # selic direction (compara meta atual com ~6m atras)
    selic_dir = 0
    try:
        hist = bcb(432, 130)
        if len(hist) > 120:
            selic_dir = 1 if hist[-1][1] > hist[0][1] else (-1 if hist[-1][1] < hist[0][1] else 0)
    except Exception:  # noqa: BLE001
        pass

    out["direcoes"] = {"selic_up": selic_dir, "usd_up": usd_dir, "ibov_up": ibov_dir, "commodity_up": commodity_dir}

    # ---- curados (sem API aberta em tempo real) ----
    out["curados"] = {
        "fluxo_estrangeiro_b3": {"texto": "Fluxo de capital estrangeiro na B3 — acompanhar boletim diário da B3 (não há API pública aberta). Em 2026 o fluxo estrangeiro tem sido o principal suporte do Ibovespa.", "tag": "curado/mensal"},
        "recuperacao_falencia": {"texto": "Recuperações judiciais e falências (Serasa Experian, mensal). Tendência de alta nos pedidos de RJ desde 2024, puxada por juros altos e endividamento de PMEs.", "tag": "curado/mensal"},
        "eleicao_2026": {"texto": "Eleições gerais em outubro/2026 (presidencial + legislativo). Ano eleitoral eleva a volatilidade e o prêmio de risco; setores regulados (energia, bancos) e fiscais sensíveis à corrida eleitoral.", "tag": "curado/contexto"},
    }

    try:
        from macro_calendar import build_macro_extras
        extras = build_macro_extras()
        p = ROOT / "fatos_relevantes_multi.json"
        if p.exists() and not extras.get("fatos_juros"):
            mj = json.loads(p.read_text()).get("macro_juros", {})
            extras["fatos_juros"] = mj.get("fatos_juros_cvm") or []
        out.update(extras)
    except Exception as e:  # noqa: BLE001
        out["agenda_macro"] = []
        out["fatos_juros"] = []
        out["leitura_juros"] = f"Agenda macro indisponível: {e}"

    return out


def main() -> None:
    out = build_macro()
    (ROOT / "macro.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    I = out["indicadores"]
    print(json.dumps({"indicadores": {k: v.get("valor") for k, v in I.items()}, "direcoes": out["direcoes"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
