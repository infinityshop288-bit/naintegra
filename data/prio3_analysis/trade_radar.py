"""Radar de day-trade em OPCOES com gestao de risco -> radar.json / /api/radar.

Regras (definidas pelo usuario):
  - Capital por trade: R$ 5.000
  - Perda maxima no dia: R$ 250 (5%)
  - Alvo minimo: +3% no capital (R$ 150), com stop-gain estendido p/ bom R:R
  - Sempre com STOP-LOSS e STOP-GAIN. Nenhuma ordem e enviada: gera-se o TICKET
    para o usuario autorizar e executar manualmente na XP.

Para cada acao: usa o vies (multi_analysis.json) p/ definir o lado (CALL/PUT),
a opcao ATM liquida (multi_options.json) p/ o ticket, e a tendencia intradia
(Yahoo 15m) p/ confirmar o timing. Premios sao referencia EOD (COTAHIST) — o
usuario confirma bid/ask ao vivo na XP antes de entrar.
"""
from __future__ import annotations

import json
import math
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent

CAPITAL = 5000.0
PERDA_MAX = 250.0          # 5% do capital — perda maxima por trade/dia
ALVO_MIN_PCT = 3.0         # ganho minimo desejado no capital
STOP_MOVE_PCT = 1.2        # movimento ADVERSO do papel que aciona o stop-loss
TARGET_MOVE_PCT = 2.4      # movimento FAVORAVEL alvo (R:R ~2:1)
LOTE = 100                 # opcoes: 1 contrato = 100 acoes


def _load(name):
    p = ROOT / name
    return json.loads(p.read_text()) if p.exists() else {}


def _delta(moneyness: str) -> float:
    return {"ATM": 0.50, "OTM": 0.38, "ITM": 0.62}.get(moneyness, 0.45)


def intraday_trends(tickers) -> dict:
    """Tendencia intradia (15m) em lote. Retorna dict por ticker."""
    out = {}
    try:
        import yfinance as yf
        import pandas as pd
        syms = [t + ".SA" for t in tickers]
        d = yf.download(syms, period="1d", interval="15m", progress=False,
                        auto_adjust=False, group_by="ticker", threads=True)
        for t in tickers:
            sym = t + ".SA"
            try:
                sub = d[sym] if isinstance(d.columns, pd.MultiIndex) else d
                c = sub["Close"].dropna(); v = sub["Volume"].fillna(0)
                if len(c) < 3:
                    out[t] = {"trend": "s/dados", "last": None}; continue
                op = float(c.iloc[0]); last = float(c.iloc[-1])
                vwap = float((c * v).sum() / v.sum()) if v.sum() > 0 else last
                slope = last - float(c.iloc[-min(4, len(c))])
                if last > op and last >= vwap and slope > 0:
                    tr = "alta"
                elif last < op and last <= vwap and slope < 0:
                    tr = "baixa"
                else:
                    tr = "lateral"
                out[t] = {"trend": tr, "last": round(last, 2), "open": round(op, 2),
                          "vwap": round(vwap, 2), "vs_vwap_pct": round((last / vwap - 1) * 100, 2)}
            except Exception:  # noqa: BLE001
                out[t] = {"trend": "s/dados", "last": None}
    except Exception:  # noqa: BLE001
        pass
    return out


def build_radar(live_quotes: dict | None = None, com_intraday: bool = True) -> dict:
    ana = _load("multi_analysis.json")
    ops = _load("multi_options.json")
    acoes = {a["ticker"]: a for a in ana.get("acoes", []) if not a.get("erro")}
    ativos = ops.get("ativos", {})

    trends = intraday_trends(list(acoes)) if com_intraday else {}

    setups = []
    for t, a in acoes.items():
        od = ativos.get(t)
        if not od:
            continue
        score = a["score"]
        lado = "CALL" if score >= 10 else ("PUT" if score <= -10 else None)
        if lado is None:
            continue
        opt = od["oportunidade"].get("call" if lado == "CALL" else "put")
        if not opt or not opt.get("premio") or opt["premio"] < 0.05:
            continue
        premio = opt["premio"]
        S = (live_quotes or {}).get(t, {}).get("price") or a["preco"]
        dia_pct = (live_quotes or {}).get(t, {}).get("pct")
        dte = None
        try:
            from datetime import date as _d
            dte = (_d.fromisoformat(opt["venc"]) - _d.today()).days
        except Exception:  # noqa: BLE001
            pass

        delta = _delta(opt.get("moneyness", "ATM"))
        # variacao do PREMIO (R$/acao) para o movimento de stop e de alvo (aprox. linear via delta)
        dprem_stop = delta * S * (STOP_MOVE_PCT / 100)      # queda de premio no stop
        dprem_alvo = delta * S * (TARGET_MOVE_PCT / 100)    # alta de premio no alvo
        if dprem_stop <= 0:
            continue
        # dimensionamento POR RISCO: perda no stop = PERDA_MAX
        contratos = int(PERDA_MAX // (dprem_stop * LOTE))
        if contratos < 1:
            continue
        # respeita o teto de capital
        max_por_capital = int(CAPITAL // (premio * LOTE))
        capado_capital = contratos > max_por_capital
        contratos = min(contratos, max_por_capital)
        if contratos < 1:
            continue
        custo = round(contratos * premio * LOTE, 2)
        elasticidade = round(delta * S / premio, 1)

        perda_rs = round(contratos * dprem_stop * LOTE, 2)
        ganho_rs = round(contratos * dprem_alvo * LOTE, 2)
        premio_stop = round(max(premio - dprem_stop, 0.01), 2)
        premio_alvo = round(premio + dprem_alvo, 2)
        rr = round(ganho_rs / perda_rs, 2) if perda_rs else None
        # parcial no alvo minimo de +3% do capital investido
        g3 = ALVO_MIN_PCT / 100
        mov_p3 = round(g3 * custo / (contratos * delta * S * LOTE) * 100, 2) if contratos else None
        premio_p3 = round(premio + g3 * custo / (contratos * LOTE), 2) if contratos else None

        it = trends.get(t, {})
        intra = it.get("trend", "s/dados")
        alinhado = (lado == "CALL" and intra == "alta") or (lado == "PUT" and intra == "baixa")
        if intra in ("lateral", "s/dados"):
            timing = "aguardar confirmação"
        elif alinhado:
            timing = "alinhado ✓"
        else:
            timing = "contra o intradia — evitar"

        setups.append({
            "ticker": t, "nome": a["nome"], "setor": a["setor"],
            "vies": score, "label": a["label"], "preco": round(S, 2), "dia_pct": dia_pct,
            "tend_diaria": a["tendencia"], "rsi": a["rsi"],
            "tend_intra": intra, "vs_vwap_pct": it.get("vs_vwap_pct"),
            "lado": lado, "alinhado": alinhado, "timing": timing,
            "opcao": {"cod": opt["cod"], "strike": opt["strike"], "venc": opt["venc"],
                      "moneyness": opt.get("moneyness"), "premio_ref": premio,
                      "dist_strike_pct": opt.get("dist_strike_pct")},
            "ticket": {
                "contratos": contratos, "custo": custo, "dte": dte,
                "entrada_ref": premio, "elasticidade": elasticidade, "delta": delta,
                "capado_por_capital": capado_capital, "rr": rr,
                "stop_gain": {"premio": premio_alvo, "ganho_rs": ganho_rs,
                              "ganho_pct_capital": round(ganho_rs / CAPITAL * 100, 1),
                              "mov_papel_pct": TARGET_MOVE_PCT},
                "stop_loss": {"premio": premio_stop, "perda_rs": perda_rs,
                              "perda_pct_capital": round(perda_rs / CAPITAL * 100, 1),
                              "mov_papel_pct": STOP_MOVE_PCT},
                "parcial_min": {"premio": premio_p3, "ganho_rs": round(custo * g3, 2),
                                "ganho_pct_capital": ALVO_MIN_PCT, "mov_papel_pct": mov_p3},
            },
            "ordens_registradas": od.get("tape_top", [])[:5],  # times&trades EOD da acao
            "pcr": od.get("termometro", {}).get("pcr_volume"),
        })

    # ranking: alinhados primeiro, depois conviccao (|vies|) e elasticidade
    setups.sort(key=lambda s: (0 if s["alinhado"] else (1 if s["timing"].startswith("aguardar") else 2),
                               -abs(s["vies"]), -s["ticket"]["elasticidade"]))
    return {
        "gerado": time.strftime("%Y-%m-%d %H:%M"),
        "regras": {"capital": CAPITAL, "perda_max_dia": PERDA_MAX, "alvo_min_pct": ALVO_MIN_PCT,
                   "stop_move_pct": STOP_MOVE_PCT, "target_move_pct": TARGET_MOVE_PCT},
        "ultimo_pregao_opcoes": ops.get("ultimo_pregao"),
        "obs": "Prêmios são referência EOD (COTAHIST). Confirme bid/ask ao vivo na XP antes de entrar. Nenhuma ordem é enviada automaticamente.",
        "setups": setups,
    }


def main() -> None:
    r = build_radar()
    (ROOT / "radar.json").write_text(json.dumps(r, indent=2, ensure_ascii=False))
    print(f"Radar gerado {r['gerado']} | setups: {len(r['setups'])}\n")
    print(f"{'Ativo':<7}{'Lado':<6}{'Viés':>5}{'Intra':<9}{'Opção':<11}{'DTE':>4}{'Prêmio':>8}{'Ctr':>5}{'Custo':>8}{'Ganho':>8}{'Perda':>8}{'R:R':>5}")
    for s in r["setups"]:
        tk = s["ticket"]; a = tk["stop_gain"]; st = tk["stop_loss"]
        print(f"{s['ticker']:<7}{s['lado']:<6}{s['vies']:>5} {s['tend_intra']:<8}{s['opcao']['cod']:<11}"
              f"{str(tk['dte']):>4}{s['opcao']['premio_ref']:>8}{tk['contratos']:>5}{tk['custo']:>8.0f}"
              f"{a['ganho_rs']:>+8.0f}{st['perda_rs']:>+8.0f}{str(tk['rr']):>5}")


if __name__ == "__main__":
    main()
