#!/usr/bin/env python3
"""Pontua o candle de PRIO3 que esta se formando agora contra o historico de giros.

Le trade_model.json (coeficientes e taxas agregadas, versionado, sem nenhum dado
pessoal), busca o candle do pregao em andamento e devolve, para CALL e para PUT,
a taxa historica de giros positivos em dias com aquele mesmo formato.

O que isto NAO e: uma previsao. A validacao em modelo_probabilidade.py testou
exatamente essa relacao fora da amostra e nao encontrou skill significativo
(39 pregoes nao dao poder estatistico para tanto). O numero aqui e descritivo --
diz como terminaram os giros feitos em dias parecidos, com o intervalo de
confianca do lado para que a largura dele fique visivel.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODELO = ROOT / "trade_model.json"
SAIDA = ROOT / "trade_signal.json"
API = ROOT / "api"

# abaixo disso a celula granular nao sustenta um numero: cai para o agregado
MIN_PREGOES = 6


def classificar(o: float, h: float, l: float, c: float) -> tuple[str, float, float]:
    """Mesmas regras de analise_candles.py — o corpo e medido antes das sombras."""
    rng = h - l
    if rng <= 0:
        return "sem amplitude", 0.0, 0.5
    corpo = abs(c - o) / rng
    topo = (h - max(o, c)) / rng
    base = (min(o, c) - l) / rng
    pos = (c - l) / rng
    alta = c >= o
    if corpo < 0.12:
        nome = "doji (indecisao)"
    elif corpo > 0.68:
        nome = "marubozu de alta" if alta else "marubozu de baixa"
    elif base >= 2 * corpo and topo <= 0.25:
        nome = "martelo (sombra inferior)"
    elif topo >= 2 * corpo and base <= 0.25:
        nome = "estrela cadente (sombra superior)"
    else:
        nome = "corpo de alta" if alta else "corpo de baixa"
    return nome, corpo, pos


def candle_de_hoje() -> dict | None:
    """OHLC do pregao em andamento (ou do ultimo fechado, fora do horario)."""
    try:
        import yfinance as yf

        d = yf.download("PRIO3.SA", period="7d", interval="1d",
                        progress=False, auto_adjust=False)
        if d is None or d.empty:
            return None
        if hasattr(d.columns, "nlevels") and d.columns.nlevels > 1:
            d.columns = d.columns.get_level_values(0)
        ult = d.iloc[-1]
        ant = d.iloc[-2] if len(d) > 1 else ult
        return {
            "data": str(d.index[-1].date()),
            "open": float(ult["Open"]), "high": float(ult["High"]),
            "low": float(ult["Low"]), "close": float(ult["Close"]),
            "prev": float(ant["Close"]),
            "fonte": "Yahoo Finance",
        }
    except Exception as e:  # noqa: BLE001
        print(f"  aviso: yfinance indisponivel ({e})", flush=True)
        return None


def brent_hoje() -> float | None:
    """Variacao do Brent no dia, do snapshot ao vivo ja existente no dashboard."""
    try:
        d = json.loads((API / "live.json").read_text())
        return float(d["quotes"]["brent"]["pct"])
    except Exception:  # noqa: BLE001
        return None


def leitura_ia(ctx: dict) -> dict:
    """Narrativa curta da IA sobre o estado de hoje. Falha em silencio."""
    try:
        import ai_providers
    except Exception:  # noqa: BLE001
        return {}
    prompt = f"""Voce le o painel de operacoes de um investidor pessoa fisica que opera
opcoes de PRIO3. Abaixo esta o estado do pregao de hoje e o historico dos giros dele.

{json.dumps(ctx, ensure_ascii=False)}

Escreva no maximo 4 frases, em portugues do Brasil, dizendo o que o candle de hoje
se parece no historico dele e o que isso sugere sobre operar CALL ou PUT agora.

Regras obrigatorias:
- Use SOMENTE os numeros do JSON acima. Nao invente padroes, ciclos, sazonalidade
  nem tendencias que nao estejam escritos ali. Se algo nao esta no JSON, nao existe.
- A validacao estatistica NAO encontrou poder preditivo (p={ctx['validacao']['p_valor']}).
  Nao escreva como se fosse previsao. Fale de semelhanca com o passado.
- Cite o numero de pregoes que sustenta a celula. Se for menos de 6, diga que e pouco.
- Mencione a largura do intervalo de confianca ao menos uma vez.
- Nao recomende compra nem venda. Nao prometa resultado.
- Sem titulo, sem lista, sem markdown. Apenas o paragrafo."""
    try:
        txt, prov = ai_providers.gerar(prompt, 400)
        return {"texto": txt.strip(), "provedor": prov}
    except Exception as e:  # noqa: BLE001
        print(f"  aviso: IA indisponivel ({e})", flush=True)
        return {}


def main() -> int:
    if not MODELO.is_file():
        print(f"[erro] {MODELO} ausente — rode trades/modelo_probabilidade.py", flush=True)
        return 1
    m = json.loads(MODELO.read_text())
    cel = m["celulas"]

    c = candle_de_hoje()
    if not c:
        SAIDA.write_text(json.dumps(
            {"erro": "sem cotacao", "gerado_em": datetime.now(timezone.utc).isoformat()},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1

    nome, corpo, pos = classificar(c["open"], c["high"], c["low"], c["close"])
    subiu = c["close"] >= c["open"]
    nivel = "cheio" if corpo > 0.68 else ("doji" if corpo < 0.12 else "medio")

    def lado(aposta_alta: bool) -> dict:
        alinhado = subiu == aposta_alta
        rot = "alinhado" if alinhado else "contra"
        granular = cel.get(f"{nivel}_{rot}")
        # celula fina so quando ela se sustenta; senao o agregado, sinalizado
        if granular and granular["pregoes"] >= MIN_PREGOES:
            base, origem = granular, f"{nivel} + {rot}"
        else:
            base, origem = cel[rot], rot
        return {
            "alinhado": alinhado,
            "probabilidade": base["taxa_giros"],
            "ic95": base["ic95"],
            "pregoes": base["pregoes"],
            "giros": base["giros"],
            "liquido": base["liquido"],
            "celula": origem,
            "celula_fina_descartada": bool(
                granular and granular["pregoes"] < MIN_PREGOES),
            "pregoes_celula_fina": (granular or {}).get("pregoes"),
        }

    brent = brent_hoje()
    agora = datetime.now(timezone(timedelta(hours=-3)))
    aberto = agora.weekday() < 5 and 10 <= agora.hour < 18 and c["data"] == str(agora.date())

    out = {
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pregao": {
            "data": c["data"],
            "em_andamento": aberto,
            "open": round(c["open"], 2), "high": round(c["high"], 2),
            "low": round(c["low"], 2), "close": round(c["close"], 2),
            "prev": round(c["prev"], 2),
            "var_pct": round(100 * (c["close"] / c["prev"] - 1), 2) if c["prev"] else None,
            "candle": nome,
            "direcao": "alta" if subiu else "baixa",
            "corpo_pct": round(100 * corpo, 1),
            "pos_na_barra": round(100 * pos, 1),
            "nivel": nivel,
            "brent_pct": brent,
            "fonte": c["fonte"],
        },
        "call": lado(True),
        "put": lado(False),
        "taxa_base": m["amostra"]["taxa_base"],
        "amostra": m["amostra"],
        "validacao": m["validacao"],
        "veredito": m["veredito"],
    }

    ctx = {k: out[k] for k in ("pregao", "call", "put", "taxa_base", "amostra", "validacao")}
    ia = leitura_ia(ctx)
    if ia:
        out["ia"] = ia

    SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  {c['data']} {nome} corpo {100*corpo:.0f}% | "
          f"CALL {out['call']['probabilidade']}% ({out['call']['celula']}) | "
          f"PUT {out['put']['probabilidade']}% ({out['put']['celula']})", flush=True)
    print(f"[OK] {SAIDA}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
