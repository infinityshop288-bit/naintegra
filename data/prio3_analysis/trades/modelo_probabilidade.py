#!/usr/bin/env python3
"""Treina o indicador de probabilidade CALL/PUT a partir dos giros reais.

Le as notas ja processadas (candles.csv + candles.json, ambos locais e fora do
versionamento) e escreve ../trade_model.json, que contem apenas coeficientes e
estatisticas agregadas -- nenhum dado pessoal, nenhuma operacao individual.
Esse arquivo e versionado porque o CI precisa dele para pontuar ao vivo sem
jamais ver as notas de corretagem.

Tres decisoes de desenho, todas forcadas pelo tamanho real da amostra:

1. A unidade e o par (pregao, aposta), nao o giro. 518 giros nascem de 39
   pregoes, e as features sao todas do dia; contar por giro multiplicaria a
   amostra por 13 e transformaria ruido em significancia.

2. As features sao escritas como ALINHAMENTO com a aposta, nao como direcao
   crua. "Candle de alta" ajuda a CALL e atrapalha a PUT; "corpo a favor"
   ajuda os dois. Com isso CALL e PUT compartilham um unico modelo, o que
   dobra a amostra util. E a mesma correcao que ja havia aparecido na analise
   de posicao na barra, onde o efeito agregado se cancelava entre os dois
   instrumentos por estar medido na direcao errada.

3. A validacao e leave-one-date-out com o pregao inteiro saindo do treino,
   CALL e PUT juntos. Deixar a CALL de um dia no treino e a PUT no teste
   vazaria o candle, que e exatamente a feature sob teste.

O ajuste e por IRLS com ridge: converge em ~8 iteracoes, o que torna viavel
refazer a validacao inteira centenas de vezes nos testes de permutacao e
bootstrap.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
SAIDA = AQUI.parent / "trade_model.json"
RIDGE = 2.0


# --- dados --------------------------------------------------------------
def carrega():
    ohlc = {c["d"]: c for c in json.loads((AQUI / "candles_grafico.json").read_text())["candles"]}
    giros = [r for r in csv.DictReader(open(AQUI / "candles.csv")) if r["classe"] == "OPCAO"]

    def num(r, k):
        v = r[k]
        return float(v) if v not in ("", "None") else None

    pares: dict[tuple[str, str], list[dict]] = {}
    for r in giros:
        pares.setdefault((r["d_entrada"], r["aposta"]), []).append(r)

    obs = []
    for (dia, aposta), gs in sorted(pares.items()):
        c = ohlc.get(dia)
        if not c:
            continue
        rng = c["high"] - c["low"]
        if rng <= 0:
            continue
        alta_aposta = aposta == "ALTA"
        subiu = c["close"] >= c["open"]
        corpo = abs(c["close"] - c["open"]) / rng
        favor = subiu == alta_aposta
        obs.append({
            "dia": dia,
            "aposta": aposta,
            "n": len(gs),
            "y": sum(1 for g in gs if num(g, "liquido") > 0) / len(gs),
            "liq": sum(num(g, "liquido") for g in gs),
            # tres codificacoes do mesmo fato, da mais grosseira a mais fina
            "bin": 1.0 if favor else 0.0,
            "tri": (1.0 if corpo > 0.68 else (0.0 if corpo < 0.12 else 0.4)) * (1 if favor else -1),
            # convicao com sinal: corpo cheio a favor = +1, corpo cheio contra = -1,
            # doji = 0 qualquer que seja a direcao (corpo nulo nao informa lado)
            "conv": corpo * (1.0 if favor else -1.0),
        })
    return obs, giros


# --- ajuste -------------------------------------------------------------
def irls(X, y, ridge=RIDGE, iters=30):
    w = np.zeros(X.shape[1])
    w[0] = np.log(max(1e-6, y.mean()) / max(1e-6, 1 - y.mean()))
    pen = np.full(X.shape[1], ridge)
    pen[0] = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        s = np.clip(p * (1 - p), 1e-6, None)
        H = X.T @ (X * s[:, None]) + np.diag(pen)
        g = X.T @ (p - y) + pen * w
        try:
            passo = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        w -= passo
        if np.max(np.abs(passo)) < 1e-9:
            break
    return w


def prob(w, conv):
    z = w[0] + w[1] * np.asarray(conv, dtype=float)
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def loo(X, y, dia):
    """Leave-one-date-out: o pregao sai inteiro, com CALL e PUT juntos."""
    pred = np.zeros(len(y))
    base = np.zeros(len(y))
    for d in np.unique(dia):
        te = dia == d
        tr = ~te
        if tr.sum() < 5:
            pred[te] = base[te] = y[tr].mean() if tr.sum() else y.mean()
            continue
        w = irls(X[tr], y[tr])
        pred[te] = 1 / (1 + np.exp(-np.clip(X[te] @ w, -30, 30)))
        base[te] = y[tr].mean()
    return pred, base


def main() -> int:
    obs, giros = carrega()
    y = np.array([o["y"] for o in obs])
    dia = np.array([o["dia"] for o in obs])
    liq = np.array([o["liq"] for o in obs])
    ngiros = np.array([o["n"] for o in obs])
    rng = np.random.default_rng(7)
    NP = 2000

    print(f"{len(giros)} giros | {len(np.unique(dia))} pregoes | {len(obs)} pares (dia, aposta)")
    print(f"taxa-base {100*y.mean():.1f}%\n")

    def avalia(nome):
        Xf = np.column_stack([np.ones(len(obs)), [o[nome] for o in obs]])
        pr, ba = loo(Xf, y, dia)
        b = float(((pr - y) ** 2).mean())
        bb_ = float(((ba - y) ** 2).mean())
        sk = 1 - b / bb_
        piores_ = 0
        for _ in range(NP):
            yp = rng.permutation(y)
            pp, bp = loo(Xf, yp, dia)
            if 1 - ((pp - yp) ** 2).mean() / ((bp - yp) ** 2).mean() >= sk:
                piores_ += 1
        pv = (piores_ + 1) / (NP + 1)
        print(f"  {nome:<5} skill {sk:+6.1%}  acerto {((pr > 0.5) == (y > 0.5)).mean():5.1%}  p = {pv:.4f}")
        return Xf, b, bb_, sk, pv, pr

    # as tres codificacoes sao testadas e TODAS reportadas: escolher a melhor e
    # so depois medir o p-valor dela seria selecionar o ruido e chama-lo de sinal
    print("Codificacoes do alinhamento (todas testadas, todas reportadas):")
    todas = {nome: avalia(nome) for nome in ("bin", "tri", "conv")}

    ESCOLHIDA = "bin"  # a mais simples; ver nota de selecao no JSON
    X, br, bb, skill, pval, pred = todas[ESCOLHIDA]
    acc = float(((pred > 0.5) == (y > 0.5)).mean())
    print(f"\npublicada: '{ESCOLHIDA}' (Brier {br:.4f} vs base {bb:.4f})")

    w = irls(X, y)
    print(f"\ncoeficientes: intercepto {w[0]:+.4f} | conv {w[1]:+.4f}")

    # bootstrap por pregao: intervalo de confianca da probabilidade prevista.
    # reamostrar pregoes (e nao pares) preserva o fato de que CALL e PUT do
    # mesmo dia compartilham o candle e por isso nao sao observacoes livres
    datas = np.unique(dia)
    grade = np.array([0.0, 1.0]) if ESCOLHIDA == "bin" else np.linspace(-1, 1, 21)
    amostras = []
    for _ in range(2000):
        esc = rng.choice(datas, size=len(datas), replace=True)
        idx = np.concatenate([np.where(dia == d)[0] for d in esc])
        try:
            wb = irls(X[idx], y[idx])
        except Exception:  # noqa: BLE001
            continue
        amostras.append(prob(wb, grade))
    A = np.array(amostras)
    lo = np.percentile(A, 2.5, axis=0)
    hi = np.percentile(A, 97.5, axis=0)

    # calibracao fora da amostra, em tercos
    ordem = np.argsort(pred)
    calib = []
    for a, b, rot in [(0, 1/3, "baixo"), (1/3, 2/3, "medio"), (2/3, 1.0, "alto")]:
        s = ordem[int(a * len(ordem)):int(b * len(ordem))]
        calib.append({
            "faixa": rot,
            "n_pares": int(len(s)),
            "n_giros": int(ngiros[s].sum()),
            "previsto": round(float(pred[s].mean()) * 100, 1),
            "realizado": round(float(y[s].mean()) * 100, 1),
            "liquido": round(float(liq[s].sum()), 2),
        })
        print(f"  calib {rot:<6} n={len(s):<3} previsto {100*pred[s].mean():5.1f}%  "
              f"realizado {100*y[s].mean():5.1f}%  liq R$ {liq[s].sum():>9,.0f}")

    # --- celulas empiricas -------------------------------------------------
    # O que vai ao ar e a taxa historica observada em cada celula, com o IC e o
    # n visiveis, e nao a curva logistica: a validacao acima mostrou que a curva
    # nao generaliza, entao apresenta-la como previsao seria inventar precisao.
    def ic_por_pregao(idx, reps=4000):
        """IC reamostrando PREGOES, nao giros.

        Um IC binomial sobre os 296 giros daria algo como [76-85]. Mas os giros
        nao sao independentes: saem de 25 pregoes, e dentro de um pregao eles
        ganham ou perdem praticamente juntos. Reamostrar o pregao inteiro
        respeita esse agrupamento -- e o intervalo que sai e varias vezes mais
        largo, que e a largura honesta.
        """
        por_dia: dict[str, list[int]] = {}
        for i in idx:
            por_dia.setdefault(obs[i]["dia"], []).append(i)
        chaves = list(por_dia)
        if len(chaves) < 2:
            return [0.0, 100.0]
        out = []
        for _ in range(reps):
            esc = rng.choice(len(chaves), size=len(chaves), replace=True)
            k = tot = 0.0
            for j in esc:
                for i in por_dia[chaves[j]]:
                    k += obs[i]["y"] * obs[i]["n"]
                    tot += obs[i]["n"]
            if tot:
                out.append(100 * k / tot)
        return [round(float(np.percentile(out, 2.5)), 1),
                round(float(np.percentile(out, 97.5)), 1)]

    def celula(sel):
        idx = [i for i, o in enumerate(obs) if sel(o)]
        if not idx:
            return None
        g = int(sum(obs[i]["n"] for i in idx))
        k = int(round(sum(obs[i]["y"] * obs[i]["n"] for i in idx)))
        lo_, hi_ = ic_por_pregao(idx)
        return {
            "pregoes": len(set(obs[i]["dia"] for i in idx)),
            "pares": len(idx),
            "giros": g,
            # taxa por giro (o que o usuario sente) e por pregao (a amostra real)
            "taxa_giros": round(100 * k / g, 1),
            "taxa_pregoes": round(100 * float(np.mean([obs[i]["y"] for i in idx])), 1),
            "ic95": [lo_, hi_],
            "liquido": round(float(sum(obs[i]["liq"] for i in idx)), 2),
        }

    def nivel(o):
        a = abs(o["conv"])
        return "cheio" if a > 0.68 else ("doji" if a < 0.12 else "medio")

    celulas = {
        "alinhado": celula(lambda o: o["bin"] == 1.0),
        "contra": celula(lambda o: o["bin"] == 0.0),
    }
    for nv in ("cheio", "medio", "doji"):
        for al, rot in ((1.0, "alinhado"), (0.0, "contra")):
            c = celula(lambda o, n=nv, a=al: nivel(o) == n and o["bin"] == a)
            if c:
                celulas[f"{nv}_{rot}"] = c

    print("\nCelulas empiricas (o que vai ao ar):")
    for k_, v in celulas.items():
        print(f"  {k_:<18} {v['pregoes']:>2} pregoes {v['giros']:>3} giros  "
              f"{v['taxa_giros']:5.1f}%  IC [{v['ic95'][0]:.0f}-{v['ic95'][1]:.0f}]  "
              f"liq R$ {v['liquido']:>9,.0f}")

    modelo = {
        "gerado_em": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "celulas": celulas,
        "veredito": (
            "SEM PODER PREDITIVO COMPROVADO. A validacao fora da amostra nao "
            "rejeitou a hipotese de que o alinhamento com o candle nao informa "
            "nada sobre o resultado. As taxas abaixo sao descritivas: dizem o que "
            "aconteceu em dias parecidos, nao o que vai acontecer."
        ) if not bool(pval < 0.05) else "Skill fora da amostra significativo a 5%.",
        "descricao": "Taxa historica de giros positivos condicionada ao alinhamento "
                     "entre a aposta e a direcao do candle do pregao.",
        "feature": "alinhado = 1 quando a direcao do candle do dia coincide com a "
                   "aposta (CALL em dia de alta, PUT em dia de baixa), 0 caso contrario",
        "codificacao": ESCOLHIDA,
        "coef": {"intercepto": round(float(w[0]), 6), "alinhado": round(float(w[1]), 6)},
        "amostra": {
            "giros": len(giros),
            "pregoes": int(len(np.unique(dia))),
            "pares": len(obs),
            "taxa_base": round(float(y.mean()) * 100, 1),
            "periodo": [min(o["dia"] for o in obs), max(o["dia"] for o in obs)],
        },
        "validacao": {
            "metodo": "leave-one-date-out (pregao inteiro fora do treino, CALL e PUT juntos)",
            "brier": round(br, 4),
            "brier_base": round(bb, 4),
            "skill": round(skill * 100, 1),
            "acerto_direcional": round(acc * 100, 1),
            "permutacoes": NP,
            "p_valor": round(pval, 4),
            "significativo": bool(pval < 0.05),
            "codificacoes_testadas": {
                k: {"skill": round(v[3] * 100, 1), "p_valor": round(v[4], 4)}
                for k, v in todas.items()
            },
            "nota_selecao": "Tres codificacoes foram testadas e as tres estao acima. "
                            "A publicada e a mais simples, nao a de maior skill: "
                            "escolher pelo resultado e depois reportar o p-valor da "
                            "escolhida seria selecionar ruido.",
        },
        "calibracao": calib,
        "banda": {
            "x": [round(float(v), 3) for v in grade],
            "p": [round(float(v) * 100, 1) for v in prob(w, grade)],
            "lo": [round(float(v) * 100, 1) for v in lo],
            "hi": [round(float(v) * 100, 1) for v in hi],
        },
    }
    SAIDA.write_text(json.dumps(modelo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n[OK] {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
