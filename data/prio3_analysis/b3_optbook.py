"""Leitura do livro de operacoes de opcoes (COTAHIST B3) + movers >10x.

Le um arquivo COTAHIST ja filtrado p/ opcoes de um ativo e gera JSON com:
  - tape: negocios do ultimo pregao disponivel (por serie), ordenado por volume.
  - movers: series cujo fechamento subiu >=10x em poucos pregoes (com liquidez).

Uso:
  python b3_optbook.py PRIO   -> le /tmp/prio_opts.txt, raw_PRIO3.csv -> b3_options.json
  python b3_optbook.py BRAV   -> le /tmp/brav_opts.txt, raw_BRAV3.csv -> b3_options_brav.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# root -> (arquivo COTAHIST filtrado, csv do ativo, ticker, json de saida)
CFG = {
    "PRIO": {"src": "/tmp/prio_opts.txt", "csv": "raw_PRIO3.csv", "ticker": "PRIO3", "out": "b3_options.json"},
    "BRAV": {"src": "/tmp/brav_opts.txt", "csv": "raw_BRAV3.csv", "ticker": "BRAV3", "out": "b3_options_brav.json"},
}


def _f(s):
    s = s.strip()
    return int(s) if s else 0


def parse(src: Path):
    regs = []
    with src.open(encoding="latin-1") as fh:
        for ln in fh:
            if len(ln) < 210:
                continue
            d = ln[2:10]
            cod = ln[12:24].strip()
            tp = ln[24:27]
            close = _f(ln[108:121]) / 100
            openp = _f(ln[56:69]) / 100
            totneg = _f(ln[147:152])
            quatot = _f(ln[152:170])
            voltot = _f(ln[170:188]) / 100
            strike = _f(ln[188:201]) / 100
            venc = ln[202:210]
            regs.append({
                "data": f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                "cod": cod, "tipo": "CALL" if tp == "070" else "PUT",
                "close": close, "open": openp, "neg": totneg, "qtd": quatot,
                "vol": voltot, "strike": strike,
                "venc": f"{venc[:4]}-{venc[4:6]}-{venc[6:8]}",
            })
    return regs


def load_underlying(csv_name: str):
    """Fechamentos diarios do ativo-objeto p/ contexto."""
    p = ROOT / csv_name
    out = {}
    if not p.exists():
        return out
    import csv
    with p.open() as fh:
        rd = csv.DictReader(fh)
        for row in rd:
            dt = (row.get("Date") or row.get("") or "")[:10]
            try:
                out[dt] = float(row.get("Close") or row.get("close"))
            except Exception:  # noqa: BLE001
                pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="PRIO", choices=list(CFG))
    cfg = CFG[ap.parse_args().root]
    regs = parse(Path(cfg["src"]))
    dates = sorted({r["data"] for r in regs})
    last = dates[-1]
    und = load_underlying(cfg["csv"])

    # ---- tape do ultimo pregao ----
    tape = [r for r in regs if r["data"] == last and r["neg"] > 0]
    tape.sort(key=lambda r: r["vol"], reverse=True)

    # ---- termometro: put/call ratio + strikes mais ativos (ultimo pregao) ----
    call_vol = sum(r["vol"] for r in tape if r["tipo"] == "CALL")
    put_vol = sum(r["vol"] for r in tape if r["tipo"] == "PUT")
    call_neg = sum(r["neg"] for r in tape if r["tipo"] == "CALL")
    put_neg = sum(r["neg"] for r in tape if r["tipo"] == "PUT")
    strike_vol = defaultdict(float)
    for r in tape:
        strike_vol[r["strike"]] += r["vol"]
    top_strikes = sorted(strike_vol.items(), key=lambda kv: kv[1], reverse=True)[:6]
    termometro = {
        "pcr_volume": round(put_vol / call_vol, 2) if call_vol else None,
        "pcr_negocios": round(put_neg / call_neg, 2) if call_neg else None,
        "call_vol": round(call_vol, 0), "put_vol": round(put_vol, 0),
        "strikes_ativos": [{"strike": k, "vol": round(v, 0)} for k, v in top_strikes],
    }
    tape_top = []
    for r in tape[:30]:
        chg = None
        if r["open"] > 0:
            chg = round((r["close"] / r["open"] - 1) * 100, 1)
        tape_top.append({
            "cod": r["cod"], "tipo": r["tipo"], "strike": r["strike"], "venc": r["venc"],
            "close": r["close"], "chg_pct": chg, "neg": r["neg"],
            "qtd": r["qtd"], "vol": round(r["vol"], 0),
        })

    # ---- movers >=10x em poucos pregoes ----
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
                dj = date.fromisoformat(b["data"])
                if (dj - di).days > 12:
                    break
                if b["neg"] < 1:
                    continue
                if b["data"] > a["venc"]:  # descarta print apos o vencimento (artefato)
                    continue
                ratio = b["close"] / a["close"]
                if best is None or ratio > best[0]:
                    best = (ratio, b, (dj - di).days, j - i)
            if best and best[0] >= 10:
                ratio, b, ddays, dsess = best
                u0 = und.get(a["data"]); u1 = und.get(b["data"])
                movers.append({
                    "cod": cod, "tipo": a["tipo"], "strike": a["strike"], "venc": a["venc"],
                    "d0": a["data"], "p0": round(a["close"], 2), "neg0": a["neg"],
                    "d1": b["data"], "p1": round(b["close"], 2), "neg1": b["neg"],
                    "mult": round(ratio, 1), "pregoes": dsess, "dias": ddays,
                    "und0": round(u0, 2) if u0 else None,
                    "und1": round(u1, 2) if u1 else None,
                    "und_var_pct": round((u1 / u0 - 1) * 100, 1) if (u0 and u1) else None,
                    "prio_var_pct": round((u1 / u0 - 1) * 100, 1) if (u0 and u1) else None,
                    "vol_pico": round(b["vol"], 0),
                })
    # dedup por serie: manter o maior multiplo
    best_by_cod = {}
    for m in movers:
        if m["cod"] not in best_by_cod or m["mult"] > best_by_cod[m["cod"]]["mult"]:
            best_by_cod[m["cod"]] = m
    movers = sorted(best_by_cod.values(), key=lambda m: m["mult"], reverse=True)

    out = {
        "fonte": "B3 COTAHIST_A2026 (fechamentos EOD por serie)",
        "ativo": cfg["ticker"],
        "ultimo_pregao": last,
        "n_series_ano": len(by),
        "n_movers_10x": len(movers),
        "termometro": termometro,
        "tape": tape_top,
        "movers": movers[:40],
    }
    (ROOT / cfg["out"]).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[{cfg['ticker']}] ultimo pregao:", last, "| series no ano:", len(by),
          "| tape(neg>0):", len(tape), "| movers>=10x:", len(movers))
    print("\nTOP 12 movers >=10x:")
    for m in movers[:12]:
        print(f"  {m['cod']:<10} {m['tipo']:<4} K{m['strike']:<6} "
              f"{m['d0']}->{m['d1']} ({m['pregoes']}p) {m['p0']:>5}->{m['p1']:>6} "
              f"= {m['mult']:>6}x | {cfg['ticker']} {m['und_var_pct']}%")


if __name__ == "__main__":
    main()
