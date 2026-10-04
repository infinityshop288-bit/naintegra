#!/usr/bin/env python3
"""As medidas de 5 min preveem melhor que o candle diario?

Compara, NA MESMA AMOSTRA, o alinhamento com o candle diario contra as medidas
tiradas do caminho intradiario. Mesmo protocolo da analise diaria:

- unidade = par (pregao, aposta), porque as features sao do dia e varios giros
  dividem o mesmo dia;
- leave-one-date-out, com o pregao inteiro fora do treino e CALL e PUT juntos;
- teste de permutacao refazendo a validacao inteira, para saber se o ganho
  sobrevive a rotulos embaralhados;
- TODAS as features testadas sao reportadas, nao so a melhor.

Restringir aos 32 pregoes com 5 min custa amostra, mas comparar features em
amostras diferentes nao diria nada.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
NPERM = 2000
RIDGE = 2.0


def num(r, k):
    v = r[k]
    return float(v) if v not in ("", "None") else None


def monta():
    f5 = json.loads((AQUI / "features_5m.json").read_text())
    ohlc = {c["d"]: c for c in
            json.loads((AQUI / "candles_grafico.json").read_text())["candles"]}
    giros = [r for r in csv.DictReader(open(AQUI / "candles.csv"))
             if r["classe"] == "OPCAO"]

    pares: dict[tuple[str, str], list[dict]] = {}
    for r in giros:
        pares.setdefault((r["d_entrada"], r["aposta"]), []).append(r)

    obs = []
    for (dia, aposta), gs in sorted(pares.items()):
        v = f5.get(dia)
        c = ohlc.get(dia)
        if not v or not c:
            continue
        rng = c["high"] - c["low"]
        if rng <= 0:
            continue
        alta = aposta == "ALTA"
        subiu_dia = c["close"] >= c["open"]
        a_favor = subiu_dia == alta
        s = 1.0 if a_favor else -1.0
        corpo = abs(c["close"] - c["open"]) / rng

        obs.append({
            "dia": dia, "aposta": aposta, "n": len(gs),
            "y": sum(1 for g in gs if num(g, "liquido") > 0) / len(gs),
            "liq": sum(num(g, "liquido") for g in gs),
            # --- referencia: o que ja estava publicado (candle diario) ---
            "diario_bin": 1.0 if a_favor else 0.0,
            "diario_conv": corpo * s,
            # --- 5 min, com sinal do alinhamento ---
            "efic": v["eficiencia"] * s,
            # --- 5 min, sem direcao: so a textura do dia ---
            "chop": v["reversoes_por_barra"],
            "percorrido": (v["percorrido_pct"] or 0) / 10.0,
            "efic_abs": v["eficiencia"],
            # --- combinacoes ---
            "efic_x_chop": v["eficiencia"] * s * (1 - v["reversoes_por_barra"]),
        })
    return obs


def irls(X, y, ridge=RIDGE, iters=30):
    w = np.zeros(X.shape[1])
    m = float(np.clip(y.mean(), 1e-6, 1 - 1e-6))
    w[0] = np.log(m / (1 - m))
    pen = np.full(X.shape[1], ridge)
    pen[0] = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        s = np.clip(p * (1 - p), 1e-6, None)
        H = X.T @ (X * s[:, None]) + np.diag(pen)
        try:
            passo = np.linalg.solve(H, X.T @ (p - y) + pen * w)
        except np.linalg.LinAlgError:
            break
        w -= passo
        if np.max(np.abs(passo)) < 1e-9:
            break
    return w


def loo(X, y, dia):
    pred = np.zeros(len(y))
    base = np.zeros(len(y))
    for d in np.unique(dia):
        te = dia == d
        tr = ~te
        if tr.sum() < 5:
            pred[te] = base[te] = y.mean()
            continue
        w = irls(X[tr], y[tr])
        pred[te] = 1 / (1 + np.exp(-np.clip(X[te] @ w, -30, 30)))
        base[te] = y[tr].mean()
    return pred, base


def main() -> int:
    obs = monta()
    y = np.array([o["y"] for o in obs])
    dia = np.array([o["dia"] for o in obs])
    liq = np.array([o["liq"] for o in obs])
    uns = np.ones(len(obs))
    rng = np.random.default_rng(11)

    print(f"{len(obs)} pares (dia, aposta) | {len(np.unique(dia))} pregoes com 5 min")
    print(f"taxa-base {100*y.mean():.1f}% | liquido total R$ {liq.sum():,.0f}\n")

    def avalia(nome, chaves):
        X = np.column_stack([uns] + [np.array([o[k] for o in obs]) for k in chaves])
        pr, ba = loo(X, y, dia)
        b = float(((pr - y) ** 2).mean())
        bb = float(((ba - y) ** 2).mean())
        sk = 1 - b / bb
        piores = 0
        for _ in range(NPERM):
            yp = rng.permutation(y)
            pp, bp = loo(X, yp, dia)
            if 1 - ((pp - yp) ** 2).mean() / ((bp - yp) ** 2).mean() >= sk:
                piores += 1
        pv = (piores + 1) / (NPERM + 1)
        marca = "  <<< significativo" if pv < 0.05 else ""
        print(f"  {nome:<34} skill {sk:+6.1%}   p = {pv:.4f}{marca}", flush=True)
        return sk, pv, pr

    print("Referencia — candle DIARIO (o que esta publicado hoje):")
    res = {}
    res["diario: alinhamento"] = avalia("alinhamento binario", ["diario_bin"])
    res["diario: conviccao"] = avalia("conviccao (corpo com sinal)", ["diario_conv"])

    print("\nCaminho de 5 MIN:")
    res["5m: eficiencia"] = avalia("eficiencia alinhada", ["efic"])
    res["5m: chop"] = avalia("ziguezague (sem direcao)", ["chop"])
    res["5m: percorrido"] = avalia("distancia percorrida", ["percorrido"])
    res["5m: efic_abs"] = avalia("eficiencia (sem direcao)", ["efic_abs"])
    res["5m: efic x chop"] = avalia("eficiencia x (1-ziguezague)", ["efic_x_chop"])

    print("\nCombinado:")
    res["5m + diario"] = avalia("eficiencia + alinhamento diario", ["efic", "diario_bin"])
    res["5m efic + chop"] = avalia("eficiencia + ziguezague", ["efic", "chop"])

    melhor = max(res, key=lambda k: res[k][0])
    print(f"\nMelhor skill: {melhor} ({res[melhor][0]:+.1%}, p={res[melhor][1]:.4f})")

    # --- taxas observadas por terco de eficiencia, por lado -------------
    print("\nTaxa observada por eficiencia do dia (contando giros):")
    ef = np.array([o["efic"] for o in obs])
    for rot, sel in (("a favor da aposta", ef > 0), ("contra a aposta", ef <= 0)):
        sub = [o for o, s_ in zip(obs, sel) if s_]
        if not sub:
            continue
        vals = sorted(abs(o["efic"]) for o in sub)
        corte = vals[len(vals) // 2]
        for faixa, cond in (("eficiente (dia limpo)", lambda o: abs(o["efic"]) > corte),
                            ("ziguezague", lambda o: abs(o["efic"]) <= corte)):
            s2 = [o for o in sub if cond(o)]
            if not s2:
                continue
            g = sum(o["n"] for o in s2)
            k = sum(o["y"] * o["n"] for o in s2)
            print(f"  {rot:<20} {faixa:<24} {len(s2):>2} pares {g:>3} giros  "
                  f"{100*k/g:5.1f}%  R$ {sum(o['liq'] for o in s2):>9,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
