"""Cruza cada operacao com o candle do ativo-objeto no dia e com o petroleo.

Para as opcoes nao se sabe a que hora do pregao o negocio saiu, mas da para
recuperar o preco da acao naquele instante: com o strike, o prazo e a
volatilidade implicita do dia, o premio pago determina o preco do ativo.
Invertendo Black-Scholes em S chega-se ao "spot implicito" da execucao -- e com
ele a posicao da entrada dentro do candle (fundo, meio ou topo do dia).

Nas operacoes a vista o preco negociado ja e o proprio preco da acao.

Responde a tres perguntas:
  - em que tipo de candle as entradas deram certo e em que tipo deram errado;
  - entrar no fundo, no meio ou no topo da barra muda o resultado;
  - acompanhar ou contrariar o movimento do Brent e do WTI ajuda.

Saida: trades/candles.csv e trades/candles_grafico.json (insumo do painel).

Uso:  python analise_candles.py
"""
from __future__ import annotations

import collections
import csv
import json
import math
import re
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SELIC = 0.1375
ATIVOS = ("PRIO3", "PETR4")


def _cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(tipo: str, s: float, k: float, t: float, r: float, vol: float) -> float:
    if t <= 0 or vol <= 0 or s <= 0:
        return max((s - k) if tipo == "CALL" else (k - s), 0.0)
    d1 = (math.log(s / k) + (r + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    desc = math.exp(-r * t)
    if tipo == "CALL":
        return s * _cdf(d1) - k * desc * _cdf(d2)
    return k * desc * _cdf(-d2) - s * _cdf(-d1)


def spot_implicito(tipo: str, premio: float, k: float, t: float, vol: float) -> float | None:
    """Inverte Black-Scholes em S: o premio e monotono no preco do ativo."""
    if premio <= 0 or vol <= 0 or t <= 0:
        return None
    lo, hi = 0.01, k * 10
    if tipo == "PUT":
        # put decresce em S; inverte o sentido da busca
        if bs(tipo, lo, k, t, SELIC, vol) < premio or bs(tipo, hi, k, t, SELIC, vol) > premio:
            return None
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if bs(tipo, mid, k, t, SELIC, vol) > premio:
                lo = mid
            else:
                hi = mid
    else:
        if bs(tipo, hi, k, t, SELIC, vol) < premio:
            return None
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if bs(tipo, mid, k, t, SELIC, vol) < premio:
                lo = mid
            else:
                hi = mid
    return 0.5 * (lo + hi)


def carregar_candles() -> dict:
    c = {}
    for nome in (*ATIVOS, "BRENT", "WTI"):
        p = AQUI / "market" / f"{nome}.csv"
        with p.open() as fh:
            for r in csv.DictReader(fh):
                try:
                    c[(nome, r["data"][:10])] = {
                        "open": float(r["open"]), "high": float(r["high"]),
                        "low": float(r["low"]), "close": float(r["close"]),
                        "ret": float(r["ret_pct"]) if r["ret_pct"] else 0.0,
                        "gap": float(r["gap_pct"]) if r["gap_pct"] else 0.0,
                        "atr_pct": float(r["atr_pct"]) if r["atr_pct"] else None,
                        "rsi": float(r["rsi14"]) if r["rsi14"] else None,
                        "mm21": float(r["mm21"]) if r["mm21"] else None,
                        "vol_rel": float(r["vol_rel"]) if r["vol_rel"] else None,
                    }
                except (ValueError, KeyError):
                    continue
    return c


def classificar(c: dict) -> str:
    rng = c["high"] - c["low"]
    if rng <= 0:
        return "sem amplitude"
    corpo = abs(c["close"] - c["open"])
    frac = corpo / rng
    topo = c["high"] - max(c["open"], c["close"])
    base = min(c["open"], c["close"]) - c["low"]
    alta = c["close"] >= c["open"]
    if frac < 0.12:
        return "doji (indecisao)"
    if frac > 0.68:
        return "marubozu de alta" if alta else "marubozu de baixa"
    if base >= 2 * corpo and topo <= 0.25 * rng:
        return "martelo (sombra inferior)"
    if topo >= 2 * corpo and base <= 0.25 * rng:
        return "estrela cadente (sombra superior)"
    return "corpo de alta" if alta else "corpo de baixa"


def terco(pos: float | None) -> str | None:
    if pos is None:
        return None
    return "1 fundo da barra" if pos < 1 / 3 else "2 meio da barra" if pos < 2 / 3 else "3 topo da barra"


def main() -> None:
    candles = carregar_candles()

    iv_de = {}
    for nome in ATIVOS:
        p = AQUI / "options" / f"{nome}.csv"
        if not p.exists():
            continue
        with p.open() as fh:
            for r in csv.DictReader(fh):
                if r["iv"]:
                    iv_de[(r["cod"], r["data"])] = (float(r["iv"]) / 100, int(r["dte"]))

    linhas = []

    # ---------- opcoes (operacoes fechadas de resultado.csv) ----------
    with (AQUI / "resultado.csv").open() as fh:
        for t in csv.DictReader(fh):
            if t["ticker"] not in ATIVOS:
                continue
            k = float(t["strike"] or 0)

            def impl(data: str, premio: float) -> float | None:
                par = iv_de.get((t["serie"], data))
                if not par or not k:
                    return None
                vol, dte = par
                return spot_implicito(t["tipo"], premio, k, dte / 365, vol)

            s_ent = impl(t["d_entrada"], float(t["p_entrada"]))
            s_sai = impl(t["d_saida"], float(t["p_saida"]))
            linhas.append({
                "classe": "OPCAO", "ativo": t["ticker"], "serie": t["serie"],
                "tipo": t["tipo"], "aposta": "ALTA" if t["tipo"] == "CALL" else "BAIXA",
                "d_entrada": t["d_entrada"], "d_saida": t["d_saida"],
                "dias": int(t["dias"]), "qtd": float(t["qtd"]),
                "liquido": float(t["liquido"]),
                "s_entrada": s_ent, "s_saida": s_sai,
            })

    # ---------- a vista (PRIO3 e PETR4) ----------
    with (AQUI / "trades.csv").open() as fh:
        vista = collections.defaultdict(list)
        for r in csv.DictReader(fh):
            if r["mercado"] != "VISTA":
                continue
            esp = re.sub(r"\s+", " ", r["especificacao"])
            tk = "PRIO3" if esp.startswith("PRIO") else "PETR4" if esp.startswith("PETROBRAS") else None
            if tk:
                vista[tk].append(r)

    for tk, ops in vista.items():
        ops.sort(key=lambda r: r["data"])
        fila: collections.deque = collections.deque()
        for r in ops:
            q, sinal, preco = float(r["quantidade"]), (1 if r["cv"] == "C" else -1), float(r["preco"])
            while q > 0 and fila and fila[0]["sinal"] != sinal:
                lote = fila[0]
                casado = min(q, lote["qtd"])
                pnl = (preco - lote["preco"]) * casado * lote["sinal"]
                linhas.append({
                    "classe": "ACAO", "ativo": tk, "serie": tk,
                    "tipo": "ACAO", "aposta": "ALTA" if lote["sinal"] > 0 else "BAIXA",
                    "d_entrada": lote["data"], "d_saida": r["data"],
                    "dias": (len({lote["data"], r["data"]}) - 1), "qtd": casado,
                    "liquido": round(pnl, 2),
                    "s_entrada": lote["preco"], "s_saida": preco,
                })
                lote["qtd"] -= casado
                q -= casado
                if lote["qtd"] <= 1e-9:
                    fila.popleft()
            if q > 0:
                fila.append({"sinal": sinal, "qtd": q, "preco": preco, "data": r["data"]})

    # ---------- enriquece com o candle e o petroleo ----------
    for L in linhas:
        c = candles.get((L["ativo"], L["d_entrada"]))
        if not c:
            continue
        rng = c["high"] - c["low"]
        L["candle"] = classificar(c)
        L["candle_dir"] = "alta" if c["close"] >= c["open"] else "baixa"
        L["ret_dia"] = c["ret"]
        L["rsi"] = c["rsi"]
        L["acima_mm21"] = (c["close"] > c["mm21"]) if c["mm21"] else None
        L["vol_rel"] = c["vol_rel"]
        L["pos_entrada"] = ((L["s_entrada"] - c["low"]) / rng
                            if L.get("s_entrada") and rng > 0 else None)
        if L["pos_entrada"] is not None:
            L["pos_entrada"] = max(0.0, min(1.0, L["pos_entrada"]))
        for ref in ("BRENT", "WTI"):
            cc = candles.get((ref, L["d_entrada"]))
            L[f"{ref.lower()}_ret"] = cc["ret"] if cc else None

        # mesmo tratamento no dia da saida: o sinal que o grafico tinha na hora
        # de encerrar e tao informativo quanto o da entrada
        cs = candles.get((L["ativo"], L["d_saida"]))
        if cs:
            rng_s = cs["high"] - cs["low"]
            L["candle_saida"] = classificar(cs)
            L["candle_saida_dir"] = "alta" if cs["close"] >= cs["open"] else "baixa"
            L["ret_dia_saida"] = cs["ret"]
            L["pos_saida"] = ((L["s_saida"] - cs["low"]) / rng_s
                              if L.get("s_saida") and rng_s > 0 else None)
            if L["pos_saida"] is not None:
                L["pos_saida"] = max(0.0, min(1.0, L["pos_saida"]))
            # na saida o alinhamento favoravel e o inverso: quem esta comprado em
            # CALL quer sair num candle de alta, nao de baixa
            L["saiu_a_favor"] = (L["aposta"] == "ALTA") == (L["candle_saida_dir"] == "alta")
            cb = candles.get(("BRENT", L["d_saida"]))
            L["brent_ret_saida"] = cb["ret"] if cb else None
        # a aposta acompanha ou contraria o candle do dia e o petroleo?
        L["a_favor_candle"] = (L["aposta"] == "ALTA") == (L["candle_dir"] == "alta")
        br = L.get("brent_ret")
        L["a_favor_brent"] = None if br is None else (L["aposta"] == "ALTA") == (br > 0)

    campos = ["classe", "ativo", "serie", "tipo", "aposta", "d_entrada", "d_saida", "dias",
              "qtd", "liquido", "s_entrada", "s_saida", "pos_entrada", "pos_saida",
              "candle", "candle_dir", "candle_saida", "candle_saida_dir",
              "ret_dia", "ret_dia_saida", "rsi", "acima_mm21", "vol_rel",
              "brent_ret", "wti_ret", "brent_ret_saida",
              "a_favor_candle", "a_favor_brent", "saiu_a_favor"]
    with (AQUI / "candles.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)

    # ---------------- relatorio ----------------
    opc = [L for L in linhas if L["classe"] == "OPCAO"]
    aco = [L for L in linhas if L["classe"] == "ACAO"]
    print(f"operacoes cruzadas com candle: {len(linhas)} "
          f"({len(opc)} em opcoes, {len(aco)} a vista)")
    com = sum(1 for L in opc if L.get("pos_entrada") is not None)
    print(f"spot implicito recuperado em {com}/{len(opc)} entradas de opcao "
          f"({com / len(opc) * 100:.0f}%)")

    def bloco(titulo, chave, universo, ordenar=True):
        print(f"\n{titulo}")
        g = collections.defaultdict(lambda: [0, 0.0, 0])
        for L in universo:
            k = chave(L)
            if k is None:
                continue
            g[k][0] += 1
            g[k][1] += L["liquido"]
            g[k][2] += 1 if L["liquido"] > 0 else 0
        itens = sorted(g.items()) if ordenar else sorted(g.items(), key=lambda kv: kv[1][1])
        for k, (n, pnl, w) in itens:
            print(f"  {str(k):<32} n={n:>3}  acerto {w / n * 100:>3.0f}%  R$ {pnl:>12,.2f}")

    print("\n" + "=" * 78)
    print("ANALISE DE CANDLE -- todas as operacoes de PRIO e PETR")
    print("=" * 78)
    bloco("candle do ativo no dia da entrada:", lambda L: L.get("candle"), linhas, ordenar=False)
    bloco("a aposta acompanha o candle do dia?:",
          lambda L: ("acompanha o candle" if L["a_favor_candle"] else "contraria o candle")
          if L.get("candle") else None, linhas)
    bloco("onde dentro da barra a entrada foi feita:",
          lambda L: terco(L.get("pos_entrada")), linhas)
    bloco("posicao do ativo frente a media de 21:",
          lambda L: None if L.get("acima_mm21") is None else
          ("acima da media de 21" if L["acima_mm21"] else "abaixo da media de 21"), linhas)

    def faixa_rsi(L):
        v = L.get("rsi")
        return None if v is None else ("1 RSI < 40" if v < 40 else "2 RSI 40-55" if v < 55
                                       else "3 RSI 55-70" if v < 70 else "4 RSI >= 70")
    bloco("RSI do ativo na entrada:", faixa_rsi, linhas)

    print("\n" + "=" * 78)
    print("O SINAL NA HORA DE SAIR")
    print("=" * 78)
    print("(na saida o alinhamento favoravel inverte: quem esta comprado em CALL")
    print(" quer encerrar num candle de alta, nao de baixa)")
    bloco("candle do ativo no dia da saida:", lambda L: L.get("candle_saida"), linhas, ordenar=False)
    bloco("a saida pegou um candle a favor da posicao?:",
          lambda L: None if L.get("saiu_a_favor") is None else
          ("saiu com o candle a favor" if L["saiu_a_favor"] else "saiu com o candle contra"), linhas)
    bloco("onde dentro da barra a saida foi feita:",
          lambda L: terco(L.get("pos_saida")), linhas)

    def ciclo(L):
        if L.get("candle") is None or L.get("saiu_a_favor") is None:
            return None
        e = "entrou a favor" if L["a_favor_candle"] else "entrou contra"
        s = "saiu a favor" if L["saiu_a_favor"] else "saiu contra"
        return f"{e} + {s}"
    bloco("ciclo completo (sinal de entrada + sinal de saida):", ciclo, linhas, ordenar=False)

    print("\n" + "=" * 78)
    print("PETROLEO -- Brent e WTI no dia da entrada")
    print("=" * 78)
    bloco("a aposta acompanha o Brent do dia?:",
          lambda L: None if L.get("a_favor_brent") is None else
          ("acompanha o Brent" if L["a_favor_brent"] else "contraria o Brent"), linhas)

    def quadrante(L):
        b, w = L.get("brent_ret"), L.get("wti_ret")
        if b is None or w is None:
            return None
        if (b > 0) == (w > 0):
            return "Brent e WTI na mesma direcao"
        return "Brent e WTI em direcoes opostas"
    bloco("Brent e WTI concordam entre si?:", quadrante, linhas)

    def comb(L):
        if L.get("candle") is None or L.get("a_favor_brent") is None:
            return None
        c = "candle a favor" if L["a_favor_candle"] else "candle contra"
        b = "Brent a favor" if L["a_favor_brent"] else "Brent contra"
        return f"{c} + {b}"
    bloco("combinacao candle + Brent:", comb, linhas, ordenar=False)

    print("\n" + "=" * 78)
    print("O SETUP COMPLETO -- candle a favor, entrada no fundo da barra, mesmo dia")
    print("=" * 78)
    for rotulo, filtro in (
        ("candle a favor + fundo da barra", lambda L: L["a_favor_candle"] and terco(L.get("pos_entrada")) == "1 fundo da barra"),
        ("candle a favor + topo da barra", lambda L: L["a_favor_candle"] and terco(L.get("pos_entrada")) == "3 topo da barra"),
        ("candle contra + fundo da barra", lambda L: not L["a_favor_candle"] and terco(L.get("pos_entrada")) == "1 fundo da barra"),
        ("candle contra + topo da barra", lambda L: not L["a_favor_candle"] and terco(L.get("pos_entrada")) == "3 topo da barra"),
    ):
        u = [L for L in linhas if L.get("candle") and L.get("pos_entrada") is not None and filtro(L)]
        if not u:
            continue
        pnl = sum(L["liquido"] for L in u)
        w = sum(1 for L in u if L["liquido"] > 0)
        print(f"  {rotulo:<34} n={len(u):>3}  acerto {w / len(u) * 100:>3.0f}%  R$ {pnl:>12,.2f}")

    print("\na vista (PRIO3 e PETR4), separado:")
    for tk in ATIVOS:
        u = [L for L in aco if L["ativo"] == tk]
        if not u:
            continue
        pnl = sum(L["liquido"] for L in u)
        w = sum(1 for L in u if L["liquido"] > 0)
        print(f"  {tk:<8} n={len(u):>3}  acerto {w / len(u) * 100:>3.0f}%  R$ {pnl:>12,.2f}")

    # ---------------- dados do grafico ----------------
    datas = sorted({d for (n, d) in candles if n == "PRIO3"})
    por_dia = collections.defaultdict(lambda: {"call": 0, "put": 0, "pnl": 0.0})
    for L in linhas:
        if L["ativo"] != "PRIO3":
            continue
        slot = por_dia[L["d_entrada"]]
        slot["call" if L["aposta"] == "ALTA" else "put"] += 1
        por_dia[L["d_saida"]]["pnl"] += L["liquido"]

    grafico = {
        "candles": [{"d": d, **{k: round(candles[("PRIO3", d)][k], 2)
                                for k in ("open", "high", "low", "close")},
                     "call": por_dia[d]["call"], "put": por_dia[d]["put"],
                     "pnl": round(por_dia[d]["pnl"], 0),
                     "brent": round(candles[("BRENT", d)]["ret"], 2) if ("BRENT", d) in candles else None,
                     "wti": round(candles[("WTI", d)]["ret"], 2) if ("WTI", d) in candles else None}
                    for d in datas],
    }
    (AQUI / "candles_grafico.json").write_text(json.dumps(grafico, ensure_ascii=False))

    # ------- uma linha por operacao, para plotar entrada e saida no preco -------
    idx = {d: i for i, d in enumerate(datas)}
    ops = []
    for L in linhas:
        if L["ativo"] != "PRIO3" or L.get("s_entrada") is None or L.get("s_saida") is None:
            continue
        if L["d_entrada"] not in idx or L["d_saida"] not in idx:
            continue
        ops.append([
            idx[L["d_entrada"]], round(L["s_entrada"], 2),
            idx[L["d_saida"]], round(L["s_saida"], 2),
            1 if L["aposta"] == "ALTA" else 0,          # CALL=1, PUT=0
            round(L["liquido"], 2),
            L["serie"],
            round(L["brent_ret"], 2) if L.get("brent_ret") is not None else None,
            round(L["brent_ret_saida"], 2) if L.get("brent_ret_saida") is not None else None,
            1 if L.get("a_favor_candle") else 0,
            1 if L.get("saiu_a_favor") else 0,
            int(L["qtd"]),
        ])
    grafico["ops"] = ops
    (AQUI / "candles_grafico.json").write_text(json.dumps(grafico, ensure_ascii=False))
    print(f"\nsalvo candles.csv ({len(linhas)}), candles_grafico.json "
          f"({len(datas)} pregoes, {len(ops)} operacoes plotaveis em PRIO3)")


if __name__ == "__main__":
    main()
