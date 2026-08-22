"""Opcoes por acao (COTAHIST) + oportunidades diarias -> multi_options.json.

Para cada ativo do universo, le /tmp/opts_{ROOT}.txt e gera:
  - n_series, movers>=10x (top), tape do ultimo pregao, termometro (pcr, strikes)
  - oportunidade do dia: CALL e PUT mais liquidas perto do dinheiro (ATM), no
    vencimento mais proximo, com premio/strike/venc/volume.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from b3_optbook import parse  # reutiliza parser COTAHIST
from universe import UNIVERSE

ROOT = Path(__file__).resolve().parent
SRC = "/tmp/opts_{root}.txt"


def price_map() -> dict:
    p = ROOT / "multi_analysis.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text())
    return {a["ticker"]: a.get("preco") for a in d.get("acoes", []) if a.get("preco")}


def termometro(tape):
    call_vol = sum(r["vol"] for r in tape if r["tipo"] == "CALL")
    put_vol = sum(r["vol"] for r in tape if r["tipo"] == "PUT")
    call_neg = sum(r["neg"] for r in tape if r["tipo"] == "CALL")
    put_neg = sum(r["neg"] for r in tape if r["tipo"] == "PUT")
    sv = defaultdict(float)
    for r in tape:
        sv[r["strike"]] += r["vol"]
    top = sorted(sv.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {"pcr_volume": round(put_vol / call_vol, 2) if call_vol else None,
            "pcr_negocios": round(put_neg / call_neg, 2) if call_neg else None,
            "call_vol": round(call_vol), "put_vol": round(put_vol),
            "strikes_ativos": [{"strike": k, "vol": round(v)} for k, v in top]}


def movers_10x(regs):
    by = defaultdict(list)
    for r in regs:
        by[r["cod"]].append(r)
    movers = []
    for cod, rows in by.items():
        rows.sort(key=lambda r: r["data"])
        n = len(rows)
        for i in range(n):
            a = rows[i]
            if a["close"] < 0.05 or a["neg"] < 1:
                continue
            di = date.fromisoformat(a["data"])
            best = None
            for j in range(i + 1, min(i + 8, n)):
                b = rows[j]
                if (date.fromisoformat(b["data"]) - di).days > 12:
                    break
                if b["neg"] < 1 or b["data"] > a["venc"]:
                    continue
                ratio = b["close"] / a["close"]
                if best is None or ratio > best[0]:
                    best = (ratio, b, j - i)
            if best and best[0] >= 10:
                ratio, b, dsess = best
                movers.append({"cod": cod, "tipo": a["tipo"], "strike": a["strike"], "venc": a["venc"],
                               "d0": a["data"], "p0": round(a["close"], 2),
                               "d1": b["data"], "p1": round(b["close"], 2),
                               "mult": round(ratio, 1), "pregoes": dsess})
    best_by = {}
    for m in movers:
        if m["cod"] not in best_by or m["mult"] > best_by[m["cod"]]["mult"]:
            best_by[m["cod"]] = m
    return sorted(best_by.values(), key=lambda m: m["mult"], reverse=True)


def opportunity(tape, last, px):
    """CALL e PUT mais liquidas perto do ATM, vencimento vivo mais proximo."""
    if not px:
        return {"call": None, "put": None}
    live = [r for r in tape if r["venc"] >= last and r["neg"] > 0]

    from datetime import date as _date
    ld = _date.fromisoformat(last)

    def pick(tipo):
        cand = [r for r in live if r["tipo"] == tipo]
        if not cand:
            return None
        vencs = sorted({r["venc"] for r in cand})
        # prefere vencimento com >=10 dias corridos (evita serie a vencer); senao o mais proximo
        futuros = [v for v in vencs if (_date.fromisoformat(v) - ld).days >= 10]
        near = futuros[0] if futuros else vencs[0]
        same = [r for r in cand if r["venc"] == near]
        # prioriza perto do dinheiro e com volume
        same.sort(key=lambda r: (abs(r["strike"] / px - 1), -r["vol"]))
        r = same[0]
        moneyness = "ATM" if abs(r["strike"] / px - 1) < 0.03 else ("OTM" if (
            (tipo == "CALL" and r["strike"] > px) or (tipo == "PUT" and r["strike"] < px)) else "ITM")
        return {"cod": r["cod"], "strike": r["strike"], "venc": r["venc"],
                "premio": round(r["close"], 2), "vol": round(r["vol"]),
                "neg": r["neg"], "moneyness": moneyness,
                "dist_strike_pct": round((r["strike"] / px - 1) * 100, 1)}

    return {"call": pick("CALL"), "put": pick("PUT")}


def main() -> None:
    prices = price_map()
    ativos = {}
    global_last = ""
    for t, (nome, setor, root) in UNIVERSE.items():
        src = Path(SRC.format(root=root))
        if not src.exists():
            continue
        regs = parse(src)
        if not regs:
            continue
        last = max(r["data"] for r in regs)
        global_last = max(global_last, last)
        tape = [r for r in regs if r["data"] == last and r["neg"] > 0]
        tape.sort(key=lambda r: r["vol"], reverse=True)
        mv = movers_10x(regs)
        px = prices.get(t)
        ativos[t] = {
            "nome": nome, "setor": setor, "root": root, "preco": px,
            "ultimo_pregao": last, "n_series": len({r["cod"] for r in regs}),
            "n_movers_10x": len(mv),
            "termometro": termometro(tape),
            "movers": mv[:8],
            "tape_top": [{"cod": r["cod"], "tipo": r["tipo"], "strike": r["strike"], "venc": r["venc"],
                          "close": round(r["close"], 2), "vol": round(r["vol"]), "neg": r["neg"],
                          "chg_pct": round((r["close"] / r["open"] - 1) * 100, 1) if r["open"] > 0 else None}
                         for r in tape[:8]],
            "oportunidade": opportunity(tape, last, px),
        }
        print(f"{t:<7} series {ativos[t]['n_series']:>4} | movers10x {len(mv):>3} | tape {len(tape):>3} | "
              f"call {ativos[t]['oportunidade']['call']['cod'] if ativos[t]['oportunidade']['call'] else '-'}")

    out = {"atualizado": date.today().isoformat(), "ultimo_pregao": global_last, "ativos": ativos}
    (ROOT / "multi_options.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print("\nsalvo multi_options.json |", len(ativos), "ativos | ultimo pregao", global_last)


if __name__ == "__main__":
    main()
