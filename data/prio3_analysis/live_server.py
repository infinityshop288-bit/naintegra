"""Servidor local para o painel PRIO3 com cotacoes em tempo real.

- Serve os arquivos estaticos do diretorio (painel.html, etc.).
- Expoe /api/live com cotacoes:
    * Brent e WTI: TradingEconomics (paginas /commodity/...), conforme pedido.
    * PRIO3: Yahoo Finance (o TradingEconomics nao cobre a acao com pagina de cotacao).
- Cache curto (~20s) para nao martelar as fontes.

Uso:  python3 live_server.py   ->   http://localhost:8899/painel.html
"""
from __future__ import annotations

import http.cookiejar
import json
import re
import ssl
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:  # usa os certificados do certifi se disponivel; senao, contexto sem verificacao
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    _SSL = ssl._create_unverified_context()

# opener com jar de cookies (ajuda a evitar 429 do Yahoo)
_JAR = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=_SSL),
    urllib.request.HTTPCookieProcessor(_JAR),
)
_yahoo_primed = False

PORT = 8899
ROOT = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

_cache: dict = {"ts": 0.0, "data": None}
CACHE_TTL = 20.0


def _get(url: str, timeout: float = 8.0, referer: str | None = None) -> str:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with _OPENER.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def _prime_yahoo() -> None:
    global _yahoo_primed
    if _yahoo_primed:
        return
    try:
        _get("https://finance.yahoo.com/quote/PRIO3.SA")
        _yahoo_primed = True
    except Exception:  # noqa: BLE001
        pass


def te_commodity(slug: str) -> dict:
    """Preco atual + variacao do dia a partir da pagina do TradingEconomics."""
    html = _get(f"https://tradingeconomics.com/commodity/{slug}")
    m = re.search(r'TEChartsMeta\s*=\s*\[\{"value":([0-9.]+)', html)
    price = float(m.group(1)) if m else None
    mp = re.search(r",\s*(up|down)\s*([0-9.]+)%\s*from the previous day", html, re.I)
    pct = None
    if mp:
        pct = float(mp.group(2)) * (1 if mp.group(1).lower() == "up" else -1)
    prev = change = None
    if price is not None and pct is not None:
        prev = price / (1 + pct / 100)
        change = price - prev
    return {"price": price, "pct": pct, "change": change, "prev": prev,
            "unit": "USD/bbl", "source": "TradingEconomics"}


def yahoo(symbol: str) -> dict:
    _prime_yahoo()
    meta = None
    last_err = None
    ref = f"https://finance.yahoo.com/quote/{symbol}"
    for host in ("query1", "query2", "query1"):
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}"
               f"?interval=1d&range=1d")
        try:
            meta = json.loads(_get(url, referer=ref))["chart"]["result"][0]["meta"]
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.8)
    if meta is None:
        try:  # fallback via yfinance (disponivel no .venv do projeto)
            import yfinance as yf

            fi = yf.Ticker(symbol).fast_info
            price = fi.get("last_price") or fi.get("lastPrice")
            prev = fi.get("previous_close") or fi.get("previousClose")
            if price is not None:
                meta = {"regularMarketPrice": price, "chartPreviousClose": prev,
                        "currency": fi.get("currency", "BRL"), "regularMarketTime": int(time.time())}
        except Exception:  # noqa: BLE001
            pass
    if meta is None:
        raise last_err or RuntimeError("Yahoo indisponível")
    price = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    pct = change = None
    if price is not None and prev:
        change = price - prev
        pct = change / prev * 100
    return {"price": price, "pct": pct, "change": change, "prev": prev,
            "unit": meta.get("currency", ""), "source": "Yahoo Finance",
            "time": meta.get("regularMarketTime")}


def crude_stocks() -> dict:
    """Variacao semanal dos estoques de petroleo dos EUA (EIA), via TradingEconomics."""
    html = _get("https://tradingeconomics.com/united-states/crude-oil-stocks-change")
    m = re.search(r'id="metaDesc"[^>]*content="([^"]+)"', html)
    txt = m.group(1) if m else ""
    mv = re.search(r"(increased|decreased|rose|fell|dropped|declined|climbed|built|drew)\s+by\s+(-?[0-9.]+)\s*million", txt, re.I)
    wk = re.search(r"week end(?:ing|ed)\s+([^.]+?)\.", txt, re.I)
    change = None
    if mv:
        val = float(mv.group(2))
        neg = mv.group(1).lower() in ("decreased", "fell", "dropped", "declined", "drew")
        change = -val if neg else val
    return {"change_mmbbl": change, "semana": (wk.group(1).strip() if wk else None),
            "fonte": "EIA (via TradingEconomics)"}


_inv_cache: dict = {"ts": 0.0, "data": None}
INV_TTL = 1800.0  # 30 min (dado semanal)


def get_inventory() -> dict:
    now = time.time()
    if not _inv_cache["data"] or now - _inv_cache["ts"] > INV_TTL:
        try:
            _inv_cache["data"] = crude_stocks()
            _inv_cache["ts"] = now
        except Exception as e:  # noqa: BLE001
            if not _inv_cache["data"]:
                _inv_cache["data"] = {"change_mmbbl": None, "error": str(e)}
    return _inv_cache["data"]


_last_good: dict = {}


def collect() -> dict:
    out = {"ts": int(time.time()), "quotes": {}}
    tasks = {
        "brent": lambda: te_commodity("brent-crude-oil"),
        "wti": lambda: te_commodity("crude-oil"),
        "prio3": lambda: yahoo("PRIO3.SA"),
        "brav3": lambda: yahoo("BRAV3.SA"),
        "usd": lambda: yahoo("USDBRL=X"),
    }
    for key, fn in tasks.items():
        try:
            q = fn()
            if q.get("price") is not None:
                _last_good[key] = q
            out["quotes"][key] = q
        except Exception as e:  # noqa: BLE001
            if key in _last_good:  # mantem ultimo valor conhecido
                stale = dict(_last_good[key])
                stale["stale"] = True
                out["quotes"][key] = stale
            else:
                out["quotes"][key] = {"error": str(e)}
    out["inventory"] = get_inventory()
    return out


def get_live() -> dict:
    now = time.time()
    if not _cache["data"] or now - _cache["ts"] > CACHE_TTL:
        _cache["data"] = collect()
        _cache["ts"] = now
    return _cache["data"]


# ----------------------- opcoes (Black-Scholes) -----------------------
import datetime as _dt
import math
from statistics import NormalDist

_N = NormalDist().cdf
_npdf = NormalDist().pdf
EXPIRY_AGO = _dt.date(2026, 8, 21)  # 3a sexta de agosto/2026 (vencimento B3)
OPT_R = 0.145   # taxa livre de risco anual (~CDI/Selic 2026)
OPT_IV = 0.50   # volatilidade implicita assumida (elevada pelo cenario geopolitico)


def _bs(S, K, T, r, sig, kind):
    if T <= 0 or sig <= 0 or S <= 0:
        intr = max(S - K, 0) if kind == "call" else max(K - S, 0)
        return {"premio": round(intr, 2), "delta": (1.0 if kind == "call" and S > K else 0.0)}
    d1 = (math.log(S / K) + (r + sig * sig / 2) * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    if kind == "call":
        premio = S * _N(d1) - K * math.exp(-r * T) * _N(d2)
        delta = _N(d1)
    else:
        premio = K * math.exp(-r * T) * _N(-d2) - S * _N(-d1)
        delta = _N(d1) - 1
    theta = (-(S * _npdf(d1) * sig) / (2 * math.sqrt(T))
             - (r * K * math.exp(-r * T) * (_N(d2) if kind == "call" else _N(-d2)))
             * (1 if kind == "call" else -1)) / 365
    return {"premio": round(max(premio, 0), 2), "delta": round(delta, 3),
            "theta_dia": round(theta, 3)}


def option_chain() -> dict:
    live = get_live()
    q = live["quotes"].get("prio3", {})
    S = q.get("price")
    today = _dt.date.today()
    dias = (EXPIRY_AGO - today).days
    T = max(dias, 0) / 365
    out = {"spot": S, "expiry": EXPIRY_AGO.isoformat(), "dias_corridos": dias,
           "iv": OPT_IV, "r": OPT_R, "linhas": [],
           "obs": "Prêmios TEÓRICOS (Black-Scholes) recalculados com o spot ao vivo; não são cotações em tempo real da B3.",
           "spot_stale": q.get("stale", False)}
    if not S:
        out["error"] = "spot indisponível"
        return out
    lo = int(math.floor(S * 0.82 / 2) * 2)
    hi = int(math.ceil(S * 1.28 / 2) * 2)
    for K in range(lo, hi + 1, 2):
        call = _bs(S, K, T, OPT_R, OPT_IV, "call")
        put = _bs(S, K, T, OPT_R, OPT_IV, "put")
        out["linhas"].append({
            "strike": K,
            "call_code": f"PRIOH{K}", "call": call, "call_be": round(K + call["premio"], 2),
            "put_code": f"PRIOT{K}", "put": put, "put_be": round(K - put["premio"], 2),
            "money": "ATM" if abs(K - S) <= 1 else ("ITM_call" if K < S else "OTM_call"),
        })
    return out


# ----------------------- projecao de day-trade -----------------------
DT_CAPITAL = 5000.0
DT_SPREAD = 0.04   # custo round-trip estimado (bid-ask) sobre o premio
LOTE = 100


def _pick_strike(S, mult):
    K = int(round(S * mult / 2) * 2)
    return max(2, K)


def _leg(S, K, T, kind):
    o = _bs(S, K, T, OPT_R, OPT_IV, kind)
    prem = o["premio"] or 0.01
    lotes = int(DT_CAPITAL // (prem * LOTE))
    shares = lotes * LOTE
    custo = round(shares * prem, 2)
    elast = round(abs(o["delta"]) * S / prem, 1)  # omega
    # movimento (%) do papel para atingir alvos de retorno sobre o capital
    def move_para(alvo_pct):
        step = 0.0005
        rng = range(0, 241) if kind == "call" else range(0, 241)
        for i in rng:
            m = i * step * (1 if kind == "call" else -1)
            nS = S * (1 + m)
            np_ = _bs(nS, K, T, OPT_R, OPT_IV, kind)["premio"]
            pl = shares * (np_ - prem) - DT_SPREAD * prem * shares
            if custo and pl / custo * 100 >= alvo_pct:
                return round(m * 100, 2)
        return None
    cen = []
    for m in (-0.03, -0.02, -0.015, -0.01, -0.005, 0, 0.005, 0.01, 0.015, 0.02, 0.03, 0.04):
        nS = S * (1 + m)
        np_ = _bs(nS, K, T, OPT_R, OPT_IV, kind)["premio"]
        pl = shares * (np_ - prem) - DT_SPREAD * prem * shares
        cen.append({"move_pct": round(m * 100, 2), "prio3": round(nS, 2),
                    "premio": round(np_, 2), "pl": round(pl, 0),
                    "pl_pct": round(pl / custo * 100, 1) if custo else 0})
    return {"tipo": kind, "code": (f"PRIOH{K}" if kind == "call" else f"PRIOT{K}"),
            "strike": K, "premio": prem, "delta": o["delta"], "theta_dia": o.get("theta_dia"),
            "lotes": lotes, "contratos": shares, "custo": custo, "elasticidade": elast,
            "move_5pct": move_para(5), "move_10pct": move_para(10), "move_20pct": move_para(20),
            "cenarios": cen}


EXPIRIES = [("2026-07-17", "PRIOG", "PRIOS"), ("2026-08-21", "PRIOH", "PRIOT")]
RV_ANUAL = 0.3931  # vol realizada 5 anos (stats_prices)


def _solve_S_for_premium(K, T, target, kind="call"):
    lo, hi = 0.01, K * 4
    for _ in range(60):
        mid = (lo + hi) / 2
        p = _bs(mid, K, T, OPT_R, OPT_IV, kind)["premio"]
        if p < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def tenx() -> dict:
    live = get_live()
    S = live["quotes"].get("prio3", {}).get("price")
    today = _dt.date.today()
    out = {"spot": S, "iv": OPT_IV, "rv": RV_ANUAL, "horizonte_dias": 3,
           "expiries": [], "obs": "Prêmios teóricos (BS). 'Mov. p/ 10x' = alta do papel para o prêmio valer 10× o de hoje em ~3 pregões. Prob. ~ risco-neutro (lognormal, IV assumida). Bilhete de loteria: a maioria expira sem valor."}
    if not S:
        out["error"] = "spot indisponível"; return out
    h = 3
    th = h / 365
    for exp, cletter, _pl in EXPIRIES:
        dte = (_dt.date.fromisoformat(exp) - today).days
        if dte <= 0:
            continue
        Ttot = dte / 365
        Texit = max((dte - h), 0.5) / 365
        em = round(OPT_IV * math.sqrt(Ttot) * 100, 1)  # movimento esperado (%) ate o venc
        cands = []
        k0 = int(math.ceil(S * 1.01))
        for K in range(k0, int(S * 1.6) + 1):
            prem0 = _bs(S, K, Ttot, OPT_R, OPT_IV, "call")["premio"]
            if prem0 < 0.03:
                continue
            alvo = 10 * prem0
            Stg = _solve_S_for_premium(K, Texit, alvo, "call")
            mv = (Stg / S - 1)
            if mv <= 0 or mv > 0.60:
                continue
            d2 = (math.log(S / Stg) + (OPT_R - 0.5 * OPT_IV ** 2) * th) / (OPT_IV * math.sqrt(th))
            prob = _N(d2)
            cands.append({"code": f"{cletter}{K}", "strike": K, "prem0": round(prem0, 2),
                          "alvo_10x": round(alvo, 2), "S_alvo": round(Stg, 2),
                          "mov_pct": round(mv * 100, 1), "prob_pct": round(prob * 100, 1)})
        cands.sort(key=lambda c: c["mov_pct"])
        out["expiries"].append({"venc": exp, "dias": dte, "serie": cletter,
                                "mov_esperado_pct": em, "candidatas": cands[:6]})
    return out


def daytrade() -> dict:
    live = get_live()
    q = live["quotes"].get("prio3", {})
    brent = live["quotes"].get("brent", {})
    S = q.get("price")
    today = _dt.date.today()
    T = max((EXPIRY_AGO - today).days, 1) / 365
    out = {"capital": DT_CAPITAL, "spot": S, "prev": q.get("prev"),
           "expiry": EXPIRY_AGO.isoformat(), "iv": OPT_IV, "r": OPT_R,
           "spread_pct": DT_SPREAD * 100, "lote": LOTE,
           "brent_pct": brent.get("pct"), "spot_stale": q.get("stale", False),
           "obs": "Prêmios teóricos (Black-Scholes); day trade = abre e fecha no mesmo pregão. Não é recomendação."}
    if not S:
        out["error"] = "spot indisponível"
        return out
    out["atm"] = _leg(S, _pick_strike(S, 1.00), T, "call")       # conservador (ATM)
    out["otm"] = _leg(S, _pick_strike(S, 1.05), T, "call")       # agressivo (OTM +5%)
    out["put"] = _leg(S, _pick_strike(S, 0.97), T, "put")        # hedge/contra-tendência
    return out


# ----------------------- analise automatizada (viés) -----------------------
def _load_json(name):
    try:
        return json.loads((ROOT / name).read_text())
    except Exception:  # noqa: BLE001
        return {}


_TECH = _load_json("technical.json")
_FV = _load_json("fair_value.json")
_STATS = _load_json("stats_prices.json")
_OPS = _load_json("operational_series.json")


def signal() -> dict:
    live = get_live()
    q = live["quotes"].get("prio3", {})
    brent = live["quotes"].get("brent", {})
    S = q.get("price") or _TECH.get("preco", 56.42)
    sma50 = _TECH.get("medias", {}).get("SMA50", 61.38)
    sma200 = _TECH.get("medias", {}).get("SMA200", 50.96)
    macd = _TECH.get("macd", {})
    rsi = _TECH.get("rsi14", 47.3)
    pos52 = _TECH.get("range_52s", {}).get("pos_pct", 58.6)
    upside = _FV.get("upside_central_pct", 25.0)
    up_cons = _FV.get("upside_consenso_pct", 25.2)
    pe_fwd = _FV.get("pe_forward", 6.1)
    prod = _OPS.get("producao_kbpd", [])
    lift = _OPS.get("lifting_cost_usd_bbl", [])
    brent_pct = brent.get("pct")

    F = []  # (categoria, nome, score[-2..2], peso, obs)

    d200 = (S / sma200 - 1) * 100
    F.append(("Técnico", "Tendência primária (MM200)",
              2 if d200 > 5 else (1 if d200 > 0 else (-1 if d200 > -5 else -2)), 1.0,
              f"preço {d200:+.1f}% vs MM200 (R$ {sma200:.2f})"))
    d50 = (S / sma50 - 1) * 100
    F.append(("Técnico", "Tendência média (MM50)",
              2 if d50 > 3 else (1 if d50 > 0 else (-1 if d50 > -5 else -2)), 1.0,
              f"preço {d50:+.1f}% vs MM50 (R$ {sma50:.2f})"))
    F.append(("Técnico", "MACD (12/26/9)",
              1 if macd.get("hist", 0) > 0 else -1, 1.0,
              f"histograma {macd.get('hist', 0):+.2f} · cruzamento {macd.get('cruzamento', '-')}"))
    F.append(("Técnico", "RSI(14)",
              -1 if rsi > 70 else (1 if rsi < 30 else 0), 1.0, f"RSI {rsi:.0f} (neutro 30–70)"))
    F.append(("Técnico", "Golden cross (MM50>MM200)",
              1 if _TECH.get("golden_cross") else -1, 1.0,
              "MM50 acima da MM200" if _TECH.get("golden_cross") else "MM50 abaixo da MM200"))
    F.append(("Técnico", "Posição na faixa de 52 semanas",
              1 if pos52 > 60 else (0 if pos52 > 40 else -1), 0.8,
              f"{pos52:.0f}% do range 52s"))

    if brent_pct is None:
        F.append(("Macro/Petróleo", "Momentum do Brent (ao vivo)", 0, 1.2, "sem dado ao vivo"))
    else:
        F.append(("Macro/Petróleo", "Momentum do Brent (ao vivo)",
                  2 if brent_pct > 2 else (1 if brent_pct > 0.3 else (0 if brent_pct > -0.3 else (-1 if brent_pct > -2 else -2))),
                  1.2, f"Brent {brent_pct:+.2f}% no dia (US$ {brent.get('price', 0):.2f})"))
    F.append(("Macro/Petróleo", "Prêmio geopolítico (Irã × EUA / Hormuz)", 1, 1.2,
              "bloqueio de Hormuz eleva preço do petróleo → positivo p/ receita da PRIO (beta ~0,5); adiciona volatilidade"))

    usd = live["quotes"].get("usd", {})
    usd_px = usd.get("price")
    usd_pct = usd.get("pct")
    if usd_px is None:
        F.append(("Macro/Petróleo", "Câmbio USD/BRL (ao vivo)", 0, 1.2, "sem dado ao vivo"))
    else:
        # Dólar ALTO favorece a PRIO (receita em US$). Nível manda; variação do dia desempata.
        USD_ALTO, USD_BAIXO = 5.20, 5.00
        if usd_px >= USD_ALTO:
            fs, nota = 1, "dólar alto → +receita em reais"
        elif usd_px <= USD_BAIXO:
            fs, nota = -1, "dólar baixo → -receita em reais"
        else:
            fs = 1 if (usd_pct or 0) > 0.3 else (-1 if (usd_pct or 0) < -0.3 else 0)
            nota = "na faixa neutra; tendência do dia " + ("de alta" if fs > 0 else ("de baixa" if fs < 0 else "estável"))
        F.append(("Macro/Petróleo", "Câmbio USD/BRL (ao vivo)", fs, 1.2,
                  f"USD/BRL {usd_px:.2f} ({(usd_pct or 0):+.2f}% no dia) — {nota}. Quanto maior o dólar, melhor p/ PRIO."))

    inv = live.get("inventory", {})
    ch = inv.get("change_mmbbl")
    if ch is None:
        F.append(("Macro/Petróleo", "Estoques de petróleo EUA (EIA)", 0, 1.0, "sem dado"))
    else:
        # queda de estoque (draw) = alta do petróleo = positivo; alta de estoque (build) = negativo
        F.append(("Macro/Petróleo", "Estoques de petróleo EUA (EIA)",
                  1 if ch < -1 else (-1 if ch > 1 else 0), 1.0,
                  f"{ch:+.1f} mi barris (sem. {inv.get('semana', '-')}) — {'queda de estoque → alta do petróleo' if ch < 0 else 'alta de estoque → pressão de baixa'}"))

    F.append(("Fundamento", "Preço-justo (modelo EV/EBITDA)",
              2 if upside > 15 else (1 if upside > 5 else (0 if upside > -5 else -2)), 1.5,
              f"upside central {upside:+.0f}% (justo R$ {_FV.get('preco_justo_central', 0):.0f})"))
    F.append(("Fundamento", "Consenso de analistas",
              2 if up_cons > 15 else (1 if up_cons > 5 else 0), 1.5,
              f"{_FV.get('consenso_analistas', {}).get('recomendacao', '-')} · alvo médio R$ {_FV.get('consenso_analistas', {}).get('alvo_medio', 0):.0f} ({up_cons:+.0f}%)"))
    F.append(("Fundamento", "Múltiplos (P/L fwd, EV/EBITDA)",
              1 if pe_fwd < 8 else (0 if pe_fwd < 12 else -1), 1.5,
              f"P/L fwd {pe_fwd:.1f}x · EV/EBITDA {_FV.get('ev_ebitda_trailing', 0):.1f}x"))
    prod_bull = len(prod) >= 2 and prod[-1] > prod[-2]
    F.append(("Fundamento", "Crescimento de produção",
              2 if prod_bull else 0, 1.5,
              f"produção {prod[-1] if prod else '-'} kbpd (Wahoo/Peregrino em rampa)" if prod else "sem série"))
    lift_bull = len(lift) >= 2 and lift[-1] < lift[-2]
    F.append(("Fundamento", "Custo de extração (lifting cost)",
              1 if lift_bull else 0, 1.0,
              f"lifting cost US$ {lift[-1]}/bbl (em queda)" if lift else "sem série"))
    ndebt = _FV.get("divida_liquida_bi"); ebit = _FV.get("ebitda_cenarios_bi", {}).get("base")
    ndeb_ratio = (ndebt / ebit) if (ndebt and ebit) else None
    F.append(("Fundamento", "Alavancagem (dívida líq./EBITDA)",
              0 if (ndeb_ratio is None or ndeb_ratio < 2) else -1, 1.0,
              f"{ndeb_ratio:.1f}x" if ndeb_ratio else "n/d"))

    num = sum(s * w for _, _, s, w, _ in F)
    den = sum(2 * w for _, _, _, w, _ in F)
    score = round(num / den * 100, 1) if den else 0
    if score >= 40:
        label, tone = "ALTA", "success"
    elif score >= 15:
        label, tone = "Leve alta", "success"
    elif score > -15:
        label, tone = "Neutro", "warning"
    elif score > -40:
        label, tone = "Leve baixa", "danger"
    else:
        label, tone = "BAIXA", "danger"

    cats: dict = {}
    for cat, _, s, w, _ in F:
        cats.setdefault(cat, [0.0, 0.0])
        cats[cat][0] += s * w
        cats[cat][1] += 2 * w
    cat_scores = {c: round(v[0] / v[1] * 100, 0) for c, v in cats.items()}

    return {"score": score, "label": label, "tone": tone, "spot": S,
            "categorias": cat_scores,
            "fatores": [{"cat": c, "nome": n, "score": s, "peso": w, "obs": o}
                        for c, n, s, w, o in F],
            "atualizado": live.get("ts")}


_mq_cache: dict = {"ts": 0.0, "data": None}
MQ_TTL = 60.0


def multiquotes() -> dict:
    """Cotacoes em lote das acoes do universo + Ibovespa (cache 60s)."""
    now = time.time()
    if _mq_cache["data"] and now - _mq_cache["ts"] < MQ_TTL:
        return _mq_cache["data"]
    out = {"ts": int(now), "quotes": {}}
    try:
        import warnings
        warnings.filterwarnings("ignore")
        import yfinance as yf
        from universe import TICKERS, yahoo_symbol
        syms = [yahoo_symbol(t) for t in TICKERS] + ["^BVSP"]
        d = yf.download(syms, period="5d", interval="1d", progress=False,
                        auto_adjust=False, group_by="ticker", threads=True)
        import pandas as pd
        for t in TICKERS + ["IBOV"]:
            sym = "^BVSP" if t == "IBOV" else yahoo_symbol(t)
            try:
                sub = d[sym] if isinstance(d.columns, pd.MultiIndex) else d
                c = sub["Close"].dropna()
                px = float(c.iloc[-1]); prev = float(c.iloc[-2])
                out["quotes"][t] = {"price": round(px, 2),
                                    "pct": round((px / prev - 1) * 100, 2),
                                    "prev": round(prev, 2)}
            except Exception:  # noqa: BLE001
                out["quotes"][t] = {"price": None}
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
    if out["quotes"]:
        _mq_cache["data"] = out
        _mq_cache["ts"] = now
    return out


_radar_cache: dict = {"ts": 0.0, "data": None}
RADAR_TTL = 120.0


def radar() -> dict:
    now = time.time()
    if _radar_cache["data"] and now - _radar_cache["ts"] < RADAR_TTL:
        return _radar_cache["data"]
    try:
        import trade_radar
        mq = multiquotes().get("quotes", {})
        data = trade_radar.build_radar(live_quotes=mq, com_intraday=True)
    except Exception as e:  # noqa: BLE001
        data = {"error": str(e), "setups": []}
    if data.get("setups") is not None and not data.get("error"):
        _radar_cache["data"] = data
        _radar_cache["ts"] = now
    return data


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def log_message(self, *a):  # silencioso
        pass

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        route = self.path.split("?")[0]
        if route == "/api/live":
            self._json(get_live()); return
        if route == "/api/options":
            self._json(option_chain()); return
        if route == "/api/signal":
            self._json(signal()); return
        if route == "/api/daytrade":
            self._json(daytrade()); return
        if route == "/api/tenx":
            self._json(tenx()); return
        if route == "/api/multiquotes":
            self._json(multiquotes()); return
        if route == "/api/radar":
            self._json(radar()); return
        super().do_GET()


if __name__ == "__main__":
    print(f"Painel com cotacoes ao vivo: http://localhost:{PORT}/painel.html")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
