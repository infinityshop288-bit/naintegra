"""Detecção de padrões e previsões com TimesFM (opcional) + fallback estatístico.

Categorias: preços de mercado, demanda/vendas (volume, produção), volatilidade,
cripto e tráfego web (pageviews Wikipedia como proxy de interesse).
Gera ai_patterns.json para o dashboard estático.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
HORIZON = 21
CTX_MIN = 60

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    _SSL = ssl._create_unverified_context()

_UA = {"User-Agent": "Mozilla/5.0 (research; prio3-ai-patterns)"}
_TIMESFM = None


def _fetch_yahoo(symbol: str, days: int = 400) -> pd.Series:
    end = datetime.today()
    start = end - timedelta(days=days + 10)
    df = yf.download(
        symbol,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )
    if df.empty:
        return pd.Series(dtype=float)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    s = df["Close"].copy()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return s.dropna()


def _fetch_volume(symbol: str, days: int = 400) -> pd.Series:
    end = datetime.today()
    start = end - timedelta(days=days + 10)
    df = yf.download(symbol, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False)
    if df.empty:
        return pd.Series(dtype=float)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    s = df["Volume"].copy()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return s.replace(0, np.nan).dropna()


def _realized_vol(close: pd.Series, win: int = 21) -> pd.Series:
    ret = close.pct_change()
    return (ret.rolling(win).std() * np.sqrt(252) * 100).dropna()


def _wiki_pageviews(article: str, days: int = 120) -> pd.Series:
    end = date.today()
    start = end - timedelta(days=days)
    url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"en.wikipedia/all-access/all-agents/{article}/daily/"
        f"{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}"
    )
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
            data = json.loads(r.read().decode())
        rows = data.get("items") or []
        if not rows:
            return pd.Series(dtype=float)
        idx = [pd.Timestamp(x["timestamp"][:8]) for x in rows]
        vals = [float(x["views"]) for x in rows]
        return pd.Series(vals, index=idx).sort_index()
    except Exception:  # noqa: BLE001
        return pd.Series(dtype=float)


def _load_csv_close(name: str) -> pd.Series:
    p = ROOT / f"raw_{name}.csv"
    if not p.is_file():
        return pd.Series(dtype=float)
    df = pd.read_csv(p, parse_dates=["Date"]).sort_values("Date")
    s = df.set_index("Date")["Close"]
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return s.dropna()


def _stat_forecast(y: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Previsão p10/p50/p90 via tendência linear + volatilidade dos resíduos."""
    y = np.asarray(y, dtype=float)
    y = y[np.isfinite(y)]
    if len(y) < CTX_MIN:
        last = float(y[-1]) if len(y) else 0.0
        z = np.full(horizon, last)
        return z * 0.95, z, z * 1.05
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    sigma = float(np.std(resid)) or abs(y[-1]) * 0.02
    fut_x = np.arange(len(y), len(y) + horizon)
    p50 = slope * fut_x + intercept
    band = 1.28 * sigma * np.sqrt(np.arange(1, horizon + 1))
    return p50 - band, p50, p50 + band


def _timesfm_forecast(y: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    global _TIMESFM
    if os.environ.get("PRIO3_USE_TIMESFM", "1") == "0":
        return None
    try:
        import timesfm  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        if _TIMESFM is None:
            _TIMESFM = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
            _TIMESFM.compile(
                timesfm.ForecastConfig(
                    max_context=min(1024, len(y)),
                    max_horizon=max(horizon, 32),
                    normalize_inputs=True,
                    use_continuous_quantile_head=True,
                )
            )
        _, q = _TIMESFM.forecast(horizon=horizon, inputs=[y.astype(np.float32)])
        q = np.asarray(q[0])
        if q.ndim == 2 and q.shape[0] >= 3:
            return q[0], q[1], q[-1]
        p50 = np.asarray(q).reshape(-1)[:horizon]
        spread = np.std(y[-60:]) * 0.5 if len(y) >= 60 else np.std(y) * 0.5
        return p50 - spread, p50, p50 + spread
    except Exception:  # noqa: BLE001
        return None


def _forecast_series(y: np.ndarray, horizon: int, engine: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    tfm = _timesfm_forecast(y, horizon) if engine != "statistical" else None
    if tfm is not None:
        return (*tfm, "timesfm-2.5")
    p10, p50, p90 = _stat_forecast(y, horizon)
    return p10, p50, p90, "statistical"


def _trend_label(y: np.ndarray) -> str:
    if len(y) < 20:
        return "indefinida"
    x = np.arange(len(y[-60:]))
    sl = np.polyfit(x, y[-60:], 1)[0]
    pct = sl / (abs(y[-1]) or 1) * len(x) * 100
    if pct > 3:
        return "alta"
    if pct < -3:
        return "baixa"
    return "lateral"


def _vol_regime(vol: float, hist: np.ndarray) -> str:
    if not len(hist):
        return "normal"
    p75 = float(np.percentile(hist, 75))
    p25 = float(np.percentile(hist, 25))
    if vol >= p75:
        return "elevada"
    if vol <= p25:
        return "baixa"
    return "normal"


def _patterns_for(id_: str, y: np.ndarray, cat: str) -> list[str]:
    out: list[str] = []
    if len(y) < 30:
        return out
    ret = np.diff(y) / (np.abs(y[:-1]) + 1e-9)
    z = (y[-1] - np.mean(y[-60:])) / (np.std(y[-60:]) + 1e-9)
    if abs(z) > 2:
        out.append(f"Anomalia: valor {'acima' if z > 0 else 'abaixo'} do normal (z={z:.1f})")
    if len(ret) >= 20:
        mom5 = y[-1] / y[-6] - 1 if len(y) > 5 else 0
        mom20 = y[-1] / y[-21] - 1 if len(y) > 21 else 0
        if mom5 > 0.03 and mom20 > 0.05:
            out.append("Momentum positivo (5d e 20d)")
        elif mom5 < -0.03 and mom20 < -0.05:
            out.append("Momentum negativo (5d e 20d)")
    if cat == "volatilidade" and y[-1] > np.percentile(y[-252:], 80):
        out.append("Regime de volatilidade alta — opções mais caras")
    if cat == "cripto" and y[-1] > np.max(y[-90:-1]):
        out.append("Novo topo em 90 dias")
    if cat == "trafego_web":
        avg = np.mean(y[-30:])
        if y[-1] > avg * 1.25:
            out.append("Pico de interesse web (+25% vs média 30d)")
    if cat == "demanda_vendas" and id_.endswith("_volume"):
        if y[-1] > np.percentile(y[-60:], 90):
            out.append("Volume acima do percentil 90 — liquidez elevada")
    return out[:4]


def _dates_from_last(last: pd.Timestamp, n: int) -> list[str]:
    d = last
    out = []
    for _ in range(n):
        d += timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append(d.strftime("%Y-%m-%d"))
    return out


def _analyze(
    id_: str,
    nome: str,
    categoria: str,
    series: pd.Series,
    unidade: str,
    engine: str,
) -> dict | None:
    s = series.dropna().astype(float)
    if len(s) < 30:
        return None
    y = s.values[-512:]
    p10, p50, p90, used = _forecast_series(y, HORIZON, engine)
    last_dt = pd.Timestamp(s.index[-1])
    fdates = _dates_from_last(last_dt, HORIZON)
    vol_hist = np.diff(y) / (np.abs(y[:-1]) + 1e-9) if len(y) > 2 else np.array([0.0])
    cur_vol = float(np.std(vol_hist[-21:]) * np.sqrt(252) * 100) if categoria != "volatilidade" else float(y[-1])
    trend = _trend_label(y)
    patterns = _patterns_for(id_, y, categoria)
    chg_fc = (p50[-1] / y[-1] - 1) * 100 if y[-1] else 0
    return {
        "id": id_,
        "nome": nome,
        "categoria": categoria,
        "unidade": unidade,
        "ultimo": round(float(y[-1]), 4),
        "ultima_data": last_dt.strftime("%Y-%m-%d"),
        "tendencia": trend,
        "vol_regime": _vol_regime(cur_vol, vol_hist * 100),
        "vol_atual_pct": round(cur_vol, 2),
        "previsao_pct_horizonte": round(chg_fc, 2),
        "engine": used,
        "confianca": round(min(0.92, 0.55 + len(y) / 800), 2),
        "padroes": patterns,
        "historico": [
            {"data": pd.Timestamp(ix).strftime("%Y-%m-%d"), "valor": round(float(v), 4)}
            for ix, v in s.tail(90).items()
        ],
        "forecast": [
            {
                "data": fdates[i],
                "p10": round(float(p10[i]), 4),
                "p50": round(float(p50[i]), 4),
                "p90": round(float(p90[i]), 4),
            }
            for i in range(HORIZON)
        ],
    }


def _operational_demand() -> pd.Series:
    p = ROOT / "operational_series.json"
    if not p.is_file():
        return pd.Series(dtype=float)
    d = json.loads(p.read_text())
    vals = d.get("producao_kbpd") or []
    if len(vals) < 4:
        return pd.Series(dtype=float)
    # Interpola trimestres em série diária sintética (proxy de tendência de produção)
    idx = pd.date_range(end=date.today(), periods=len(vals) * 30, freq="D")
    rep = np.repeat(vals, 30)[: len(idx)]
    return pd.Series(rep, index=idx)


def _correlations(items: list[dict]) -> list[dict]:
    by_id = {x["id"]: np.array([h["valor"] for h in x["historico"]]) for x in items if x.get("historico")}
    keys = ["prio3_preco", "brent_preco", "btc_preco", "prio3_vol", "wiki_petroleo"]
    out = []
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            if a not in by_id or b not in by_id:
                continue
            x, y = by_id[a], by_id[b]
            n = min(len(x), len(y))
            if n < 20:
                continue
            c = float(np.corrcoef(x[-n:], y[-n:])[0, 1])
            out.append({"a": a, "b": b, "corr_90d": round(c, 3)})
    return sorted(out, key=lambda r: -abs(r["corr_90d"]))[:8]


def build_ai_patterns(engine: str = "auto") -> dict:
    eng = "statistical" if engine == "statistical" else "auto"
    specs: list[tuple[str, str, str, pd.Series, str]] = []

    prio3 = _load_csv_close("PRIO3")
    if prio3.empty:
        prio3 = _fetch_yahoo("PRIO3.SA")
    brent = _load_csv_close("BRENT")
    if brent.empty:
        brent = _fetch_yahoo("BZ=F")
    ibov = _fetch_yahoo("^BVSP")
    usd = _fetch_yahoo("USDBRL=X")
    btc = _fetch_yahoo("BTC-USD")
    eth = _fetch_yahoo("ETH-USD")
    vol_prio3 = _realized_vol(prio3) if len(prio3) else pd.Series(dtype=float)
    vol_brent = _realized_vol(brent) if len(brent) else pd.Series(dtype=float)
    vol_prio3_s = _fetch_volume("PRIO3.SA")
    wiki_oil = _wiki_pageviews("Petroleum")
    wiki_btc = _wiki_pageviews("Bitcoin")
    wiki_prio = _wiki_pageviews("Petrobras")
    prod = _operational_demand()

    specs += [
        ("prio3_preco", "PRIO3", "precos_mercado", prio3, "BRL"),
        ("brent_preco", "Brent", "precos_mercado", brent, "USD/bbl"),
        ("ibov_preco", "Ibovespa", "precos_mercado", ibov, "pts"),
        ("usd_preco", "USD/BRL", "precos_mercado", usd, "BRL"),
        ("btc_preco", "Bitcoin", "cripto", btc, "USD"),
        ("eth_preco", "Ethereum", "cripto", eth, "USD"),
        ("prio3_vol", "Vol. PRIO3 (realizada 21d)", "volatilidade", vol_prio3, "% a.a."),
        ("brent_vol", "Vol. Brent (realizada 21d)", "volatilidade", vol_brent, "% a.a."),
        ("prio3_volume", "Volume PRIO3 (demanda/liquidez)", "demanda_vendas", vol_prio3_s, "papéis"),
        ("wiki_petroleo", "Interesse web — Petróleo", "trafego_web", wiki_oil, "pageviews/d"),
        ("wiki_bitcoin", "Interesse web — Bitcoin", "trafego_web", wiki_btc, "pageviews/d"),
        ("wiki_petrobras", "Interesse web — Petrobras", "trafego_web", wiki_prio, "pageviews/d"),
        ("prio3_producao", "Produção PRIO (trim.)", "demanda_vendas", prod, "kbpd"),
    ]

    items = []
    engines_used: set[str] = set()
    for id_, nome, cat, ser, unit in specs:
        row = _analyze(id_, nome, cat, ser, unit, eng)
        if row:
            items.append(row)
            engines_used.add(row["engine"])

    insights = []
    p = next((x for x in items if x["id"] == "prio3_preco"), None)
    b = next((x for x in items if x["id"] == "brent_preco"), None)
    v = next((x for x in items if x["id"] == "prio3_vol"), None)
    c = next((x for x in items if x["id"] == "btc_preco"), None)
    if p and b:
        insights.append(
            f"PRIO3 tendência {p['tendencia']} vs Brent {b['tendencia']} — "
            f"previsão PRIO3 {p['previsao_pct_horizonte']:+.1f}% em {HORIZON} pregões."
        )
    if v:
        insights.append(f"Volatilidade PRIO3 em regime {v['vol_regime']} ({v['vol_atual_pct']:.1f}% a.a.).")
    if c:
        insights.append(f"Bitcoin {c['tendencia']}; previsão {c['previsao_pct_horizonte']:+.1f}% no horizonte.")
    wiki = next((x for x in items if x["id"] == "wiki_petroleo"), None)
    if wiki and wiki.get("padroes"):
        insights.append(f"Tráfego web: {wiki['padroes'][0]}.")

    primary_engine = "timesfm-2.5" if "timesfm-2.5" in engines_used else "statistical"

    return {
        "gerado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "horizon_dias": HORIZON,
        "engine": primary_engine,
        "engines": sorted(engines_used),
        "nota": (
            "TimesFM 2.5 (Google) quando disponível; senão fallback estatístico. "
            "Volume = proxy de demanda/liquidez; Wikipedia = proxy de tráfego web."
        ),
        "categorias": {
            "precos_mercado": "Preços e índices",
            "demanda_vendas": "Demanda, volume e produção",
            "volatilidade": "Volatilidade realizada",
            "cripto": "Criptoativos",
            "trafego_web": "Interesse web (Wikipedia)",
        },
        "insights": insights,
        "correlacoes": _correlations(items),
        "series": items,
    }


def main() -> None:
    out = build_ai_patterns()
    path = ROOT / "ai_patterns.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] {path} — {len(out['series'])} séries · engine={out['engine']}")


if __name__ == "__main__":
    main()
