"""Monitor em (quase) tempo real das principais ROTAS DE TRANSPORTE DE PETROLEO.

Fonte: IMF PortWatch (dados diarios derivados de AIS, sem chave). Para cada
chokepoint relevante ao petroleo, mede os transitos de PETROLEIROS (n_tanker) e
o total, calcula media 7d vs baseline 90d (desvio %), a fatia de petroleiros e um
STATUS (reduzido / normal / elevado) — quedas fortes de transito costumam sinalizar
disrupcao de oferta (altista p/ petroleo e exportadoras: PRIO3, BRAV3).

Complementa com o contexto de fluxo de oleo (EIA, referencia estatica em Mb/d) e
gera oil_routes.json p/ o painel. O mapa AIS ao vivo (nivel de navio) e o
MarineTraffic — embutir e bloqueado, entao o painel abre por link.
"""
from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    _SSL = ssl._create_unverified_context()

ROOT = Path(__file__).resolve().parent
BASE = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
        "Daily_Chokepoints_Data/FeatureServer/0/query")

# chokepoints relevantes ao petroleo (ordem de importancia p/ oleo), com contexto EIA
CHOKES = [
    {"id": "chokepoint6", "nome": "Estreito de Ormuz", "regiao": "Golfo Pérsico",
     "mbd": 20.0, "papel": "~20 Mb/d de petróleo (≈1/3 do óleo marítimo mundial); saída do Golfo (Arábia, Irã, Iraque, EAU, Kuwait). Sem rota alternativa relevante."},
    {"id": "chokepoint5", "nome": "Estreito de Malaca", "regiao": "Sudeste Asiático",
     "mbd": 23.0, "papel": "~23 Mb/d de petróleo e derivados rumo à Ásia (China, Japão, Coreia)."},
    {"id": "chokepoint4", "nome": "Bab-el-Mandeb", "regiao": "Mar Vermelho",
     "mbd": 8.0, "papel": "~8 Mb/d; porta do Mar Vermelho/Suez. Ataques houthis desviaram fluxo p/ o Cabo."},
    {"id": "chokepoint1", "nome": "Canal de Suez", "regiao": "Egito",
     "mbd": 9.0, "papel": "~9 Mb/d (com o oleoduto SUMED); ligação Golfo/Ásia–Europa."},
    {"id": "chokepoint7", "nome": "Cabo da Boa Esperança", "regiao": "África do Sul",
     "mbd": 7.0, "papel": "Rota de desvio quando o Mar Vermelho está sob risco; alonga viagens e frete."},
    {"id": "chokepoint3", "nome": "Bósforo (Estreitos Turcos)", "regiao": "Turquia",
     "mbd": 3.0, "papel": "~3 Mb/d; escoamento de petróleo russo e do Cáspio p/ o Mediterrâneo."},
    {"id": "chokepoint2", "nome": "Canal do Panamá", "regiao": "Panamá",
     "mbd": 1.5, "papel": "~1,5 Mb/d; GLP/derivados entre Atlântico e Pacífico. Sensível a secas."},
]


def fetch(portid: str, n: int = 150):
    params = {
        "where": f"portid='{portid}'",
        "outFields": "date,portname,n_tanker,n_total,capacity_tanker,capacity",
        "returnGeometry": "false", "f": "json",
        "orderByFields": "date DESC", "resultRecordCount": str(n),
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "prio3-analysis"})
    with urllib.request.urlopen(req, timeout=60, context=_SSL) as r:
        d = json.loads(r.read().decode("utf-8", "ignore"))
    rows = [f["attributes"] for f in d.get("features", [])]
    for x in rows:  # date dateOnly vem como epoch ms
        dt = x.get("date")
        if isinstance(dt, (int, float)):
            x["ymd"] = date.fromtimestamp(dt / 1000).isoformat()
        else:
            x["ymd"] = str(dt)[:10]
    rows.sort(key=lambda z: z["ymd"])  # cronologico
    return rows


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def analisa(rows):
    if not rows:
        return None
    tk = [r.get("n_tanker") for r in rows]
    tot = [r.get("n_total") for r in rows]
    cap = [r.get("capacity_tanker") for r in rows]
    a7, a30, a90 = mean(tk[-7:]), mean(tk[-30:]), mean(tk[-90:])
    dev = round((a7 / a90 - 1) * 100, 1) if (a7 is not None and a90) else None
    share = round(mean(tk[-7:]) / mean(tot[-7:]) * 100, 0) if (mean(tk[-7:]) is not None and mean(tot[-7:])) else None
    if dev is None:
        status = "sem dado"
    elif dev <= -25:
        status = "reduzido"
    elif dev >= 20:
        status = "elevado"
    else:
        status = "normal"
    spark = [r.get("n_tanker") or 0 for r in rows[-30:]]
    return {
        "ultimo_dia": rows[-1]["ymd"], "n_tanker": rows[-1].get("n_tanker"),
        "n_total": rows[-1].get("n_total"),
        "media_7d": round(a7, 1) if a7 is not None else None,
        "media_30d": round(a30, 1) if a30 is not None else None,
        "media_90d": round(a90, 1) if a90 is not None else None,
        "desvio_pct": dev, "fatia_petroleiros_pct": share,
        "capacity_tanker_7d": round(mean(cap[-7:])) if mean(cap[-7:]) is not None else None,
        "status": status, "spark": spark, "n_dias": len(rows),
    }


def main() -> None:
    saida = []
    piores = []
    for c in CHOKES:
        try:
            rows = fetch(c["id"])
            st = analisa(rows)
        except Exception as e:  # noqa: BLE001
            st = None
            print(f"  {c['nome']}: erro {e}")
        rec = {**c, "dados": st}
        saida.append(rec)
        if st and st["desvio_pct"] is not None:
            piores.append((c["nome"], st["desvio_pct"], st["status"]))
        if st:
            print(f"  {c['nome']:<28} tanker7d {st['media_7d']} (base {st['media_90d']}) "
                  f"desvio {st['desvio_pct']}% -> {st['status']} | fatia {st['fatia_petroleiros_pct']}% | ult {st['ultimo_dia']}")

    hz = next((r["dados"] for r in saida if r["id"] == "chokepoint6"), None)
    reduzidos = [p for p in piores if p[2] == "reduzido"]
    if hz and hz["status"] == "reduzido":
        risco = "ELEVADO"
        resumo = ("Trânsito de petroleiros no Estreito de Ormuz abaixo do normal — sinal de possível "
                  "restrição de oferta. Cenário altista para o petróleo e favorável a exportadoras "
                  "(PRIO3, BRAV3); atenção a prêmio de risco no Brent.")
    elif reduzidos:
        risco = "MODERADO"
        nomes = ", ".join(p[0] for p in reduzidos)
        resumo = (f"Fluxo reduzido em: {nomes}. Pressão pontual sobre rotas/frete; efeito altista "
                  "moderado no petróleo. Ormuz operando dentro do normal.")
    else:
        risco = "BAIXO"
        resumo = ("Trânsito de petroleiros dentro da normalidade nos principais chokepoints. "
                  "Sem prêmio de risco logístico relevante sobre o petróleo no momento.")

    out = {
        "atualizado": date.today().isoformat(),
        "fonte": "IMF PortWatch (trânsitos diários por AIS) + contexto EIA de fluxo de óleo",
        "mapa_ao_vivo": "https://www.marinetraffic.com/en/ais/home/centerx:56.7/centery:25.9/zoom:4",
        "risco_rota": risco, "resumo": resumo,
        "chokepoints": saida,
    }
    (ROOT / "oil_routes.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nRISCO DE ROTA: {risco}\nsalvo oil_routes.json | {len(saida)} chokepoints")


if __name__ == "__main__":
    main()
