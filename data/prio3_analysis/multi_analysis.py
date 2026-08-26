"""Analise automatizada de todas as acoes do universo -> multi_analysis.json.

Por acao: tecnicos (MM50/200, RSI, tendencia, 52s, retornos, vol), sentimento de
analistas (Yahoo: recomendacao + preco-alvo), tilt macro setorial (usa macro.json)
e um VIES composto (-100..+100), alem de potencial de alta/baixa (alvo e tecnico).

Inclui ainda, por ativo:
  - faixa SEMANAL e MENSAL (maxima/minima da semana e do mes correntes + anteriores)
    e a posicao do preco dentro de cada faixa (0% = no piso / 100% = no teto);
  - FLUXO DE MERCADO: Money Flow Index (MFI, RSI ponderado por volume), direcao do
    dinheiro nos ultimos 5 pregoes e Put/Call Ratio de opcoes (multi_options.json);
  - VEREDITO barato/caro: combina a posicao nas faixas (semana/mes/52s) com o fluxo
    (MFI + distancia da MM200) num score -100 (barato) .. +100 (caro).

Alem do vetor "acoes", grava:
  - "ibovespa": monitor do Indice Bovespa (^BVSP) com a VERTENTE do mercado
    (ALTISTA / BAIXISTA / NEUTRA), placar -100..+100, medias, RSI, MFI, faixas,
    retornos e sinais tecnicos comentados;
  - "segmentos": leitura agregada por setor;
  - "destaques": melhores oportunidades / mais baratos / mais esticados.
"""
from __future__ import annotations

import json
import time
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

from universe import UNIVERSE, SECTOR_TILT, yahoo_symbol  # noqa: E402

ROOT = Path(__file__).resolve().parent


def rsi(s: pd.Series, n: int = 14) -> float:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn
    return float((100 - 100 / (1 + rs)).iloc[-1])


def mfi(df: pd.DataFrame, n: int = 14):
    """Money Flow Index: RSI ponderado por volume (fluxo de dinheiro).
    >80 sobrecomprado (caro) / <20 sobrevendido (barato)."""
    try:
        tp = (df["High"] + df["Low"] + df["Close"]) / 3
        rmf = tp * df["Volume"]
        up = tp.diff() > 0
        pos = rmf.where(up, 0.0).rolling(n).sum()
        neg = rmf.where(~up, 0.0).rolling(n).sum()
        ratio = pos / neg.replace(0, np.nan)
        val = 100 - 100 / (1 + ratio)
        v = float(val.iloc[-1])
        return round(v, 1) if v == v else None
    except Exception:  # noqa: BLE001
        return None


def money_flow_5d(df: pd.DataFrame):
    """Fluxo liquido de dinheiro nos ultimos 5 pregoes, em % do fluxo bruto.
    Positivo = entrada liquida (compradores); negativo = saida (vendedores)."""
    try:
        tp = (df["High"] + df["Low"] + df["Close"]) / 3
        raw = tp * df["Volume"]
        signed = np.sign(tp.diff()) * raw
        net = float(signed.iloc[-5:].sum())
        gross = float(raw.iloc[-5:].sum())
        return round(net / gross * 100, 1) if gross else None
    except Exception:  # noqa: BLE001
        return None


def clip(x, lo=-100, hi=100):
    return max(lo, min(hi, x))


def load_hist() -> dict:
    """Baixa OHLCV (1 ano, diario) de todo o universo. Retorna dict de DataFrames."""
    syms = [yahoo_symbol(t) for t in UNIVERSE]
    d = yf.download(syms, period="1y", interval="1d", progress=False,
                    auto_adjust=False, group_by="ticker", threads=True)
    out = {}
    for t in UNIVERSE:
        sym = yahoo_symbol(t)
        try:
            sub = d[sym] if isinstance(d.columns, pd.MultiIndex) else d
            sub = sub.dropna(subset=["Close"])
            if len(sub) > 60:
                out[t] = sub
        except Exception:  # noqa: BLE001
            pass
    for t in UNIVERSE:  # retry faltantes individualmente
        if t in out:
            continue
        for _ in range(2):
            h = yf.download(yahoo_symbol(t), period="1y", interval="1d", progress=False, auto_adjust=False)
            if isinstance(h.columns, pd.MultiIndex):
                h.columns = h.columns.get_level_values(0)
            h = h.dropna(subset=["Close"])
            if len(h) > 60:
                out[t] = h
                break
            time.sleep(1.0)
    return out


def period_hilo(df: pd.DataFrame, freq: str):
    """Maxima/minima do periodo corrente e do anterior (freq 'W' ou 'M')."""
    key = df.index.to_period(freq)
    hi = df["High"].groupby(key).max()
    lo = df["Low"].groupby(key).min()
    cur_hi, cur_lo = float(hi.iloc[-1]), float(lo.iloc[-1])
    prev_hi = float(hi.iloc[-2]) if len(hi) > 1 else None
    prev_lo = float(lo.iloc[-2]) if len(lo) > 1 else None
    return cur_hi, cur_lo, prev_hi, prev_lo


def pos_in_range(px, lo, hi):
    """Posicao do preco na faixa: 0% no piso, 100% no teto."""
    if hi is None or lo is None or hi <= lo:
        return None
    return round((px - lo) / (hi - lo) * 100, 0)


def analyst(t: str) -> dict:
    try:
        info = yf.Ticker(yahoo_symbol(t)).info
        mean = info.get("recommendationMean")
        target = info.get("targetMeanPrice")
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        n = info.get("numberOfAnalystOpinions")
        up = round((target / price - 1) * 100, 1) if (target and price) else None
        return {"rec": info.get("recommendationKey"), "mean": mean, "target": target,
                "n": n, "upside_pct": up}
    except Exception:  # noqa: BLE001
        return {"rec": None, "mean": None, "target": None, "n": None, "upside_pct": None}


def tec_score(px, sma50, sma200, r_rsi, ret1m, dist200):
    sc = 0.0
    if px > sma50 > sma200:
        sc += 40
    elif px < sma50 < sma200:
        sc -= 40
    else:
        sc += 15 if px > sma200 else -15
    sc += clip((ret1m or 0) * 3, -25, 25)
    if r_rsi > 72:
        sc -= 15
    elif r_rsi < 28:
        sc += 15
    if dist200 is not None and dist200 > 30:
        sc -= 15
    return clip(sc)


def macro_score(setor, dirs):
    tilt = SECTOR_TILT.get(setor, {})
    if not tilt or not dirs:
        return 0.0
    num = sum(tilt.get(k, 0) * dirs.get(k, 0) for k in tilt)
    den = sum(abs(v) for v in tilt.values()) or 1
    return clip(num / den * 100)


def analyst_score(a):
    mean = a.get("mean"); up = a.get("upside_pct")
    if mean is None and up is None:
        return None
    parts, w = 0.0, 0.0
    if mean is not None:
        parts += (3 - mean) / 2 * 100 * 0.6; w += 0.6
    if up is not None:
        parts += clip(up * 3) * 0.4; w += 0.4
    return clip(parts / w) if w else None


def label_of(score):
    return "ALTA" if score >= 30 else ("BAIXA" if score <= -30 else "NEUTRO")


def valuation(px, pos_month, pos_52w, mfi_v, dist200, pcr):
    """Barato/caro a partir do fluxo do mercado.
    Combina onde o preco esta na faixa (mes + 52s) com o fluxo (MFI, MM200).
    Score -100 (barato) .. +100 (caro)."""
    comp = []
    if pos_month is not None:
        comp.append((0.40, pos_month * 2 - 100))     # posicao no mes
    if pos_52w is not None:
        comp.append((0.25, pos_52w * 2 - 100))       # posicao em 52 semanas
    if mfi_v is not None:
        comp.append((0.20, (mfi_v - 50) * 2))         # fluxo de dinheiro (MFI)
    comp.append((0.15, clip((dist200 or 0) * 3)))     # esticamento vs MM200
    wsum = sum(w for w, _ in comp) or 1
    score = clip(sum(w * v for w, v in comp) / wsum)
    if score >= 60:
        nivel, tag = "Muito caro", "CARO"
    elif score >= 25:
        nivel, tag = "Caro", "CARO"
    elif score > -25:
        nivel, tag = "Preço justo", "JUSTO"
    elif score > -60:
        nivel, tag = "Barato", "BARATO"
    else:
        nivel, tag = "Muito barato", "BARATO"
    return {"score": round(score), "tag": tag, "nivel": nivel}


def flow_label(mfi_v, mf5d, pcr):
    if mfi_v is None:
        base = "sem dados"
    elif mfi_v >= 60:
        base = "comprador forte"
    elif mfi_v >= 52:
        base = "comprador"
    elif mfi_v <= 40:
        base = "vendedor forte"
    elif mfi_v <= 48:
        base = "vendedor"
    else:
        base = "equilibrado"
    return {"mfi": mfi_v, "mf5d_pct": mf5d, "pcr_opcoes": pcr, "direcao": base}


def load_pcr() -> dict:
    p = ROOT / "multi_options.json"
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text())
        return {t: (v.get("termometro", {}) or {}).get("pcr_volume")
                for t, v in d.get("ativos", {}).items()}
    except Exception:  # noqa: BLE001
        return {}


def load_fatos_recentes(dias: int = 45) -> dict:
    """Ultimo Fato Relevante de cada empresa, se recente (<= `dias`)."""
    p = ROOT / "fatos_relevantes_multi.json"
    if not p.exists():
        return {}
    try:
        from datetime import date
        d = json.loads(p.read_text()); out = {}
        for tk, e in d.get("empresas", {}).items():
            fatos = e.get("fatos") or []
            if not fatos:
                continue
            f = fatos[0]
            try:
                dd = (date.today() - date.fromisoformat(f["data"])).days
            except Exception:  # noqa: BLE001
                continue
            if dd <= dias:
                out[tk] = {"data": f["data"], "assunto": f["assunto"], "dias": dd}
        return out
    except Exception:  # noqa: BLE001
        return {}


# leitura consolidada: cruza tendencia (label) x valuation (barato/caro) -> sinal acionavel
_MATRIX = {
    ("ALTA", "BARATO"): ("FORTE_COMPRA", "Barato e em alta — janela de compra"),
    ("ALTA", "JUSTO"): ("COMPRA", "Tendência de alta a preço justo"),
    ("ALTA", "CARO"): ("CAUTELA", "Alta esticada — aguardar recuo"),
    ("NEUTRO", "BARATO"): ("COMPRA", "Descontado — acumular/observar"),
    ("NEUTRO", "JUSTO"): ("NEUTRO", "Sem assimetria clara"),
    ("NEUTRO", "CARO"): ("CAUTELA", "Esticado sem tendência — cautela"),
    ("BAIXA", "BARATO"): ("OBSERVAR", "Caindo, mas barato — esperar fundo/reversão"),
    ("BAIXA", "JUSTO"): ("EVITAR", "Tendência fraca — evitar"),
    ("BAIXA", "CARO"): ("EVITAR", "Caro e em baixa — evitar"),
}


def consolidado(score, label, val, mfi_v):
    sinal, zona = _MATRIX.get((label, val["tag"]), ("NEUTRO", "—"))
    flow = ((mfi_v - 50) * 2) if mfi_v is not None else 0
    opp = clip(0.45 * (-val["score"]) + 0.35 * score + 0.20 * flow)
    return {"sinal": sinal, "zona": zona, "oportunidade": round((opp + 100) / 2)}


def analisa_ibov():
    """Monitor do Indice Bovespa (^BVSP): tendencia, medias, RSI, MFI, momentum ->
    vertente ALTISTA / BAIXISTA / NEUTRA com placar -100..+100 e leitura textual."""
    d = None
    for _ in range(3):
        try:
            d = yf.download("^BVSP", period="1y", interval="1d", progress=False, auto_adjust=False)
        except Exception:  # noqa: BLE001
            d = None
        if d is not None and len(d):
            break
        time.sleep(1.0)
    if d is None or not len(d):
        return None
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.dropna(subset=["Close"])
    if len(d) < 60:
        return None
    s = d["Close"]
    px = float(s.iloc[-1]); prev = float(s.iloc[-2])
    chg = round((px / prev - 1) * 100, 2)
    sma20 = float(s.rolling(20).mean().iloc[-1])
    sma50 = float(s.rolling(50).mean().iloc[-1])
    sma200 = float(s.rolling(min(200, len(s))).mean().iloc[-1])
    rr = round(rsi(s), 1)
    mfi_v = mfi(d)
    dist50 = round((px / sma50 - 1) * 100, 1)
    dist200 = round((px / sma200 - 1) * 100, 1)
    hi52 = float(s.iloc[-252:].max()); lo52 = float(s.iloc[-252:].min())
    pos52 = pos_in_range(px, lo52, hi52)
    wk_hi, wk_lo, wk_phi, wk_plo = period_hilo(d, "W")
    mo_hi, mo_lo, mo_phi, mo_plo = period_hilo(d, "M")
    pos_w = pos_in_range(px, wk_lo, wk_hi)
    pos_m = pos_in_range(px, mo_lo, mo_hi)
    ret1w = round((px / s.iloc[-6] - 1) * 100, 1) if len(s) > 6 else None
    ret1m = round((px / s.iloc[-22] - 1) * 100, 1) if len(s) > 22 else None
    ret3m = round((px / s.iloc[-63] - 1) * 100, 1) if len(s) > 63 else None
    yr = s.index[-1].year; ytd_base = s[s.index >= f"{yr}-01-01"]
    ytd = round((px / float(ytd_base.iloc[0]) - 1) * 100, 1) if len(ytd_base) else None

    sc = 0.0
    if px > sma50 > sma200:
        sc += 40
    elif px < sma50 < sma200:
        sc -= 40
    else:
        sc += 15 if px > sma200 else -15
    sc += 18 if px > sma20 else -18
    sc += clip((ret1m or 0) * 3, -18, 18)
    if rr > 72:
        sc -= 12
    elif rr < 28:
        sc += 12
    if mfi_v is not None:
        sc += clip((mfi_v - 50) * 0.5, -12, 12)
    sc = round(clip(sc))
    if sc >= 30:
        vert = "ALTISTA"
    elif sc <= -30:
        vert = "BAIXISTA"
    else:
        vert = "NEUTRA"
    trend = "alta" if px > sma50 > sma200 else ("baixa" if px < sma50 < sma200 else "lateral")

    sinais = []
    sinais.append(("Preço vs MM50/200",
                   "acima das duas médias" if px > sma50 and px > sma200 else
                   ("abaixo das duas médias" if px < sma50 and px < sma200 else "entre as médias"),
                   "up" if px > sma50 and px > sma200 else ("down" if px < sma50 and px < sma200 else "neu")))
    sinais.append(("Cruzamento MM50×MM200",
                   "MM50 acima da MM200 (golden)" if sma50 > sma200 else "MM50 abaixo da MM200 (death)",
                   "up" if sma50 > sma200 else "down"))
    sinais.append(("RSI (14)",
                   f"{rr} — sobrecomprado" if rr > 70 else (f"{rr} — sobrevendido" if rr < 30 else f"{rr} — neutro"),
                   "down" if rr > 70 else ("up" if rr < 30 else "neu")))
    if mfi_v is not None:
        sinais.append(("Fluxo (MFI)",
                       f"{mfi_v} — dinheiro entrando" if mfi_v >= 55 else (f"{mfi_v} — dinheiro saindo" if mfi_v <= 45 else f"{mfi_v} — equilibrado"),
                       "up" if mfi_v >= 55 else ("down" if mfi_v <= 45 else "neu")))
    sinais.append(("Momentum (1 mês)",
                   f"{ret1m:+.1f}%" if ret1m is not None else "—",
                   "up" if (ret1m or 0) > 0 else ("down" if (ret1m or 0) < 0 else "neu")))

    if vert == "ALTISTA":
        resumo = ("Vertente altista: índice acima das médias com fluxo/momentum a favor. "
                  "Tende a favorecer posições compradas; cautela apenas se RSI/MFI muito esticados.")
    elif vert == "BAIXISTA":
        resumo = ("Vertente baixista: índice pressionado abaixo das médias, com fluxo/momentum negativos. "
                  "Ambiente de aversão a risco — priorizar defesa e evitar comprar na tendência de queda.")
    else:
        resumo = ("Vertente neutra/lateral: sem tendência dominante. Índice oscila entre suportes e resistências; "
                  "operar por faixas e aguardar rompimento com volume.")

    spark = [round(float(v), 0) for v in s.iloc[-30:].tolist()]
    return {
        "indice": "IBOVESPA", "simbolo": "^BVSP",
        "pontos": round(px), "variacao_dia_pct": chg,
        "vertente": vert, "score": sc, "tendencia": trend,
        "resumo": resumo,
        "mm20": round(sma20), "mm50": round(sma50), "mm200": round(sma200),
        "dist_mm50_pct": dist50, "dist_mm200_pct": dist200,
        "rsi": rr, "mfi": mfi_v,
        "high52": round(hi52), "low52": round(lo52), "pos_52w_pct": pos52,
        "semana": {"high": round(wk_hi), "low": round(wk_lo), "pos_pct": pos_w},
        "mes": {"high": round(mo_hi), "low": round(mo_lo), "pos_pct": pos_m},
        "ret_1s": ret1w, "ret_1m": ret1m, "ret_3m": ret3m, "ret_ytd": ytd,
        "sinais": sinais, "spark": spark,
    }


def _asset_stats(s):
    """Estatisticas de tendencia p/ um indice/ativo global (serie de fechamentos)."""
    s = s.dropna()
    if len(s) < 30:
        return None
    px = float(s.iloc[-1]); prev = float(s.iloc[-2])
    chg = round((px / prev - 1) * 100, 2)
    sma50 = float(s.rolling(min(50, len(s))).mean().iloc[-1])
    sma200 = float(s.rolling(min(200, len(s))).mean().iloc[-1])
    rr = round(rsi(s), 1)
    ret1w = round((px / s.iloc[-6] - 1) * 100, 1) if len(s) > 6 else None
    ret1m = round((px / s.iloc[-22] - 1) * 100, 1) if len(s) > 22 else None
    ret3m = round((px / s.iloc[-63] - 1) * 100, 1) if len(s) > 63 else None
    yr = s.index[-1].year; base = s[s.index >= f"{yr}-01-01"]
    ytd = round((px / float(base.iloc[0]) - 1) * 100, 1) if len(base) else None
    sc = 0.0
    if px > sma50 > sma200:
        sc += 42
    elif px < sma50 < sma200:
        sc -= 42
    else:
        sc += 16 if px > sma200 else -16
    sc += clip((ret1m or 0) * 3, -22, 22)
    sc += 12 if px > sma50 else -12
    if rr > 72:
        sc -= 10
    elif rr < 28:
        sc += 10
    sc = round(clip(sc))
    trend = "alta" if px > sma50 > sma200 else ("baixa" if px < sma50 < sma200 else "lateral")
    spark = [round(float(v), 2) for v in s.iloc[-30:].tolist()]
    return {"preco": px, "var_dia_pct": chg, "ret_1s": ret1w, "ret_1m": ret1m,
            "ret_3m": ret3m, "ret_ytd": ytd, "rsi": rr, "score": sc, "tendencia": trend,
            "spark": spark}


def mercados_globais():
    """Bitcoin, juro dos EUA (10 anos), bolsas americana e europeia + influencia no Brasil."""
    syms = ["BTC-USD", "^TNX", "^GSPC", "^IXIC", "^STOXX50E", "^GDAXI"]
    data = {}
    try:
        d = yf.download(syms, period="1y", interval="1d", progress=False,
                        auto_adjust=False, group_by="ticker", threads=True)
        for sym in syms:
            try:
                sub = d[sym]["Close"] if isinstance(d.columns, pd.MultiIndex) else d["Close"]
                st = _asset_stats(sub)
                if st:
                    data[sym] = st
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    for sym in syms:  # retry individuais
        if sym in data:
            continue
        try:
            h = yf.download(sym, period="1y", interval="1d", progress=False, auto_adjust=False)
            if isinstance(h.columns, pd.MultiIndex):
                h.columns = h.columns.get_level_values(0)
            st = _asset_stats(h["Close"])
            if st:
                data[sym] = st
        except Exception:  # noqa: BLE001
            pass

    def dir_txt(sc, up="alta", down="baixa", flat="lateral"):
        return up if sc >= 25 else (down if sc <= -25 else flat)

    META = {
        "BTC-USD": {"nome": "Bitcoin", "classe": "Cripto / risco global", "unid": "US$", "dec": 0,
                    "vert": "cripto"},
        "^TNX": {"nome": "Juro EUA 10 anos", "classe": "Treasury 10Y (rendimento)", "unid": "%", "dec": 2,
                 "vert": "juros"},
        "^GSPC": {"nome": "S&P 500", "classe": "Bolsa EUA", "unid": "pts", "dec": 0, "vert": "bolsa"},
        "^IXIC": {"nome": "Nasdaq", "classe": "Bolsa EUA (tech)", "unid": "pts", "dec": 0, "vert": "bolsa"},
        "^STOXX50E": {"nome": "Euro Stoxx 50", "classe": "Bolsa Europa", "unid": "pts", "dec": 0, "vert": "bolsa"},
        "^GDAXI": {"nome": "DAX (Alemanha)", "classe": "Bolsa Europa", "unid": "pts", "dec": 0, "vert": "bolsa"},
    }

    itens = []
    for sym in syms:
        st = data.get(sym)
        meta = META[sym]
        if not st:
            itens.append({"simbolo": sym, **meta, "dados": None, "vertente": None, "influencia": "sem dado"})
            continue
        sc = st["score"]
        if meta["vert"] == "juros":
            # para juros, 'score' alto = rendimento subindo
            vert = "SUBINDO" if sc >= 25 else ("CAINDO" if sc <= -25 else "ESTÁVEL")
            if vert == "SUBINDO":
                inf = ("Juro longo dos EUA em alta fortalece o dólar e drena capital de emergentes — "
                       "PRESSÃO sobre o Ibovespa e o real, e sobre setores sensíveis a juros (varejo, construção).")
            elif vert == "CAINDO":
                inf = ("Juro longo dos EUA em queda enfraquece o dólar e favorece fluxo para emergentes — "
                       "APOIO ao Ibovespa, ao real e a ativos de risco brasileiros.")
            else:
                inf = "Juro longo dos EUA estável — sem novo impulso direcional para o fluxo a emergentes."
        elif meta["vert"] == "cripto":
            vert = dir_txt(sc, "ALTISTA", "BAIXISTA", "NEUTRA")
            if vert == "ALTISTA":
                inf = ("Bitcoin em alta sinaliza apetite a risco global ('risk-on'), que costuma "
                       "acompanhar entrada de capital em bolsas emergentes como a B3.")
            elif vert == "BAIXISTA":
                inf = ("Bitcoin em queda sugere aversão a risco ('risk-off') — ambiente menos favorável "
                       "a fluxo para ativos de risco, incluindo a B3.")
            else:
                inf = "Bitcoin sem tendência clara — sinal neutro de apetite a risco."
        else:
            vert = dir_txt(sc, "ALTISTA", "BAIXISTA", "NEUTRA")
            reg = "americana" if sym in ("^GSPC", "^IXIC") else "europeia"
            if vert == "ALTISTA":
                inf = (f"Bolsa {reg} em alta melhora o humor global e tende a puxar o Ibovespa por "
                       "correlação e fluxo estrangeiro.")
            elif vert == "BAIXISTA":
                inf = (f"Bolsa {reg} em queda piora o humor global e tende a pressionar o Ibovespa "
                       "e o apetite por emergentes.")
            else:
                inf = f"Bolsa {reg} sem tendência definida — influência neutra sobre a B3."
        itens.append({"simbolo": sym, **meta, "dados": st, "vertente": vert, "influencia": inf})

    # ambiente externo p/ o Brasil: bolsas + cripto favoraveis; juro subindo desfavoravel
    def sc_of(sym):
        return data[sym]["score"] if sym in data else 0
    externo = clip(0.30 * sc_of("^GSPC") + 0.12 * sc_of("^IXIC") + 0.18 * sc_of("^STOXX50E")
                   + 0.10 * sc_of("^GDAXI") + 0.10 * sc_of("BTC-USD") - 0.30 * sc_of("^TNX"))
    externo = round(externo)
    if externo >= 25:
        amb, resumo = "FAVORÁVEL", ("Ambiente externo favorável ao Brasil: bolsas globais firmes e/ou juro americano cedendo "
                                    "sustentam o apetite a risco e o fluxo estrangeiro para a B3.")
    elif externo <= -25:
        amb, resumo = "DESFAVORÁVEL", ("Ambiente externo adverso: fraqueza das bolsas globais e/ou juro americano em alta "
                                       "drenam risco de emergentes e pressionam Ibovespa e real.")
    else:
        amb, resumo = "NEUTRO", ("Ambiente externo misto/neutro: sinais globais divididos, sem viés externo dominante "
                                 "sobre a B3 no momento.")
    return {"ambiente_externo": {"score": externo, "label": amb, "resumo": resumo}, "ativos": itens}


def build_segmentos(acoes):
    by = defaultdict(list)
    for a in acoes:
        if not a.get("erro"):
            by[a["setor"]].append(a)
    segs = []
    for setor, itens in by.items():
        n = len(itens)
        avg_score = round(sum(x["score"] for x in itens) / n)
        vals = [x["valuation"]["score"] for x in itens if x.get("valuation")]
        avg_val = round(sum(vals) / len(vals)) if vals else 0
        mfis = [x["fluxo"]["mfi"] for x in itens if x.get("fluxo", {}).get("mfi") is not None]
        avg_mfi = round(sum(mfis) / len(mfis), 1) if mfis else None
        tag = "CARO" if avg_val >= 25 else ("BARATO" if avg_val <= -25 else "JUSTO")
        segs.append({
            "setor": setor, "n_ativos": n,
            "vies_medio": avg_score,
            "label": label_of(avg_score),
            "valuation_medio": avg_val, "valuation_tag": tag,
            "mfi_medio": avg_mfi,
            "n_alta": sum(1 for x in itens if x["label"] == "ALTA"),
            "n_baixa": sum(1 for x in itens if x["label"] == "BAIXA"),
            "n_barato": sum(1 for x in itens if x.get("valuation", {}).get("tag") == "BARATO"),
            "n_caro": sum(1 for x in itens if x.get("valuation", {}).get("tag") == "CARO"),
            "tilt": SECTOR_TILT.get(setor, {}),
            "ativos": [x["ticker"] for x in sorted(itens, key=lambda z: z["score"], reverse=True)],
        })
    segs.sort(key=lambda s: s["vies_medio"], reverse=True)
    return segs


def build_multi_analysis(fresh_macro: bool = False, tickers: list[str] | None = None) -> dict:
    macro = {}
    if fresh_macro:
        try:
            from macro import build_macro
            macro = build_macro()
        except Exception:  # noqa: BLE001
            fresh_macro = False
    if not macro:
        p = ROOT / "macro.json"
        if p.exists():
            macro = json.loads(p.read_text())
    dirs = macro.get("direcoes", {})
    pcr_map = load_pcr()
    fatos_map = load_fatos_recentes()
    ibov = analisa_ibov()
    globais = mercados_globais()

    universe_items = UNIVERSE.items()
    if tickers:
        universe_items = [(t, UNIVERSE[t]) for t in tickers if t in UNIVERSE]

    hist = load_hist()
    acoes = []
    for t, (nome, setor, root) in universe_items:
        df = hist.get(t)
        if df is None:
            acoes.append({"ticker": t, "nome": nome, "setor": setor, "erro": "sem dados"})
            continue
        s = df["Close"].dropna()
        px = float(s.iloc[-1])
        sma50 = float(s.rolling(50).mean().iloc[-1])
        sma200 = float(s.rolling(min(200, len(s))).mean().iloc[-1])
        r = s.pct_change()
        vol = float(r.iloc[-252:].std() * np.sqrt(252) * 100)
        hi52 = float(s.iloc[-252:].max()); lo52 = float(s.iloc[-252:].min())
        ret1m = round((px / s.iloc[-22] - 1) * 100, 1) if len(s) > 22 else None
        ret3m = round((px / s.iloc[-63] - 1) * 100, 1) if len(s) > 63 else None
        yr = s.index[-1].year
        ytd_base = s[s.index >= f"{yr}-01-01"]
        ytd = round((px / float(ytd_base.iloc[0]) - 1) * 100, 1) if len(ytd_base) else None
        dist200 = round((px / sma200 - 1) * 100, 1)
        rr = round(rsi(s), 1)
        trend = "alta" if px > sma50 > sma200 else ("baixa" if px < sma50 < sma200 else "lateral")
        # suporte/resistencia (swing 60d + 52s)
        sw_hi = float(s.iloc[-60:].max()); sw_lo = float(s.iloc[-60:].min())
        resist = min(x for x in [hi52, sw_hi] if x > px) if any(x > px for x in [hi52, sw_hi]) else hi52
        supp = max(x for x in [sma200, sw_lo] if x < px) if any(x < px for x in [sma200, sw_lo]) else sma200

        # faixas semanal / mensal
        wk_hi, wk_lo, wk_phi, wk_plo = period_hilo(df, "W")
        mo_hi, mo_lo, mo_phi, mo_plo = period_hilo(df, "M")
        pos_w = pos_in_range(px, wk_lo, wk_hi)
        pos_m = pos_in_range(px, mo_lo, mo_hi)
        pos_52 = pos_in_range(px, lo52, hi52)

        # fluxo de mercado
        mfi_v = mfi(df)
        mf5d = money_flow_5d(df)
        pcr = pcr_map.get(t)
        fluxo = flow_label(mfi_v, mf5d, pcr)
        val = valuation(px, pos_m, pos_52, mfi_v, dist200, pcr)

        a = analyst(t)
        ts = tec_score(px, sma50, sma200, rr, ret1m, dist200)
        ms = macro_score(setor, dirs)
        asx = analyst_score(a)
        if asx is None:
            score = round(0.65 * ts + 0.35 * ms)
        else:
            score = round(0.45 * ts + 0.25 * ms + 0.30 * asx)
        pot_alta = round((resist / px - 1) * 100, 1)
        pot_baixa = round((supp / px - 1) * 100, 1)
        leitura = consolidado(score, label_of(score), val, mfi_v)
        spark = [round(float(v), 2) for v in s.iloc[-30:].tolist()]

        acoes.append({
            "ticker": t, "nome": nome, "setor": setor, "root": root,
            "preco": round(px, 2), "ret_1m": ret1m, "ret_3m": ret3m, "ret_ytd": ytd,
            "rsi": rr, "sma50": round(sma50, 2), "sma200": round(sma200, 2),
            "dist200_pct": dist200, "tendencia": trend, "vol_anual_pct": round(vol, 1),
            "high52": round(hi52, 2), "low52": round(lo52, 2), "pos_52w_pct": pos_52,
            "semana": {"high": round(wk_hi, 2), "low": round(wk_lo, 2), "pos_pct": pos_w,
                       "prev_high": round(wk_phi, 2) if wk_phi else None,
                       "prev_low": round(wk_plo, 2) if wk_plo else None},
            "mes": {"high": round(mo_hi, 2), "low": round(mo_lo, 2), "pos_pct": pos_m,
                    "prev_high": round(mo_phi, 2) if mo_phi else None,
                    "prev_low": round(mo_plo, 2) if mo_plo else None},
            "fluxo": fluxo, "valuation": val, "consolidado": leitura,
            "fato_recente": fatos_map.get(t),
            "spark": spark,
            "suporte": round(supp, 2), "resistencia": round(resist, 2),
            "potencial_alta_pct": pot_alta, "potencial_baixa_pct": pot_baixa,
            "analistas": a,
            "score": score, "label": label_of(score),
            "componentes": {"tecnico": round(ts), "macro": round(ms),
                            "analista": round(asx) if asx is not None else None},
        })

    segmentos = build_segmentos(acoes)

    ok = [a for a in acoes if not a.get("erro")]

    def brief(a):
        return {"ticker": a["ticker"], "nome": a["nome"], "setor": a["setor"], "preco": a["preco"],
                "sinal": a["consolidado"]["sinal"], "zona": a["consolidado"]["zona"],
                "oportunidade": a["consolidado"]["oportunidade"],
                "valuation_tag": a["valuation"]["tag"], "valuation_score": a["valuation"]["score"],
                "nivel": a["valuation"]["nivel"], "mfi": a["fluxo"]["mfi"],
                "vies": a["score"], "label": a["label"],
                "fato_recente": a.get("fato_recente")}
    destaques = {
        "melhores_oportunidades": [brief(a) for a in sorted(ok, key=lambda z: z["consolidado"]["oportunidade"], reverse=True)[:5]],
        "mais_esticados": [brief(a) for a in sorted(ok, key=lambda z: z["valuation"]["score"], reverse=True)[:5]],
        "mais_baratos": [brief(a) for a in sorted(ok, key=lambda z: z["valuation"]["score"])[:5]],
        "fluxo_comprador": [brief(a) for a in sorted([a for a in ok if a["fluxo"]["mfi"] is not None], key=lambda z: z["fluxo"]["mfi"], reverse=True)[:5]],
        "com_fato_recente": [brief(a) for a in ok if a.get("fato_recente")],
    }

    out = {"atualizado": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
           "ibovespa": ibov, "mercados_globais": globais,
           "direcoes_macro": dirs, "destaques": destaques, "segmentos": segmentos, "acoes": acoes}
    return out


def main() -> None:
    out = build_multi_analysis()
    acoes = out["acoes"]
    ibov = out["ibovespa"]
    globais = out["mercados_globais"]
    segmentos = out["segmentos"]
    (ROOT / "multi_analysis.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))

    if ibov:
        print(f"\nIBOVESPA {ibov['pontos']:,} pts ({ibov['variacao_dia_pct']:+.2f}%) -> "
              f"VERTENTE {ibov['vertente']} (placar {ibov['score']:+d}) | "
              f"MM50 {ibov['mm50']:,} MM200 {ibov['mm200']:,} | RSI {ibov['rsi']} MFI {ibov['mfi']} | "
              f"1m {ibov['ret_1m']}% YTD {ibov['ret_ytd']}%")
    if globais:
        ae = globais["ambiente_externo"]
        print(f"\nMERCADOS GLOBAIS | Ambiente externo: {ae['label']} (placar {ae['score']:+d})")
        for it in globais["ativos"]:
            d = it["dados"]
            if not d:
                print(f"  {it['nome']:<18} sem dado"); continue
            print(f"  {it['nome']:<18}{d['preco']:>12,.2f} {it['unid']:<4} ({d['var_dia_pct']:+.2f}%) "
                  f"{str(it['vertente']):<9} 1m {d['ret_1m']}% YTD {d['ret_ytd']}%")

    print(f"{'Ticker':<7}{'Setor':<18}{'Preço':>8}{'MFI':>5}{'Valu':>6} {'Verd.':<7}"
          f"{'Viés':>6}{'Opp':>5} {'Sinal':<13}Zona")
    for x in acoes:
        if "erro" in x:
            print(f"{x['ticker']:<7}{x['setor']:<18}  --- sem dados ---"); continue
        c = x["consolidado"]
        print(f"{x['ticker']:<7}{x['setor']:<18}{x['preco']:>8}{str(x['fluxo']['mfi']):>5}"
              f"{x['valuation']['score']:>6} {x['valuation']['tag']:<7}{x['score']:>6}{c['oportunidade']:>5} "
              f"{c['sinal']:<13}{c['zona']}")
    print("\nSegmentos (viés médio | valuation médio):")
    for sgv in segmentos:
        print(f"  {sgv['setor']:<18} viés {sgv['vies_medio']:>4} {sgv['label']:<7} | "
              f"valuation {sgv['valuation_medio']:>4} {sgv['valuation_tag']:<7} | "
              f"barato {sgv['n_barato']}/caro {sgv['n_caro']} | MFI {sgv['mfi_medio']}")


if __name__ == "__main__":
    main()
