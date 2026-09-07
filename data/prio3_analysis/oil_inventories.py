"""Estoques de petróleo — EUA (EIA semanal) e panorama global (OECD/IEA).

Fonte principal: TradingEconomics (meta EIA/API). Variação semanal em milhões
de barris; queda (draw) = pressão de alta no preço; alta (build) = pressão de baixa.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    _SSL = ssl._create_unverified_context()

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

# slug TE -> metadados
TE_WEEKLY = [
    {
        "id": "us_crude",
        "slug": "united-states/crude-oil-stocks-change",
        "nome": "EUA — petróleo bruto",
        "regiao": "Estados Unidos",
        "fonte": "EIA",
        "unidade": "M barris/sem",
    },
    {
        "id": "us_gasoline",
        "slug": "united-states/gasoline-stocks-change",
        "nome": "EUA — gasolina",
        "regiao": "Estados Unidos",
        "fonte": "EIA",
        "unidade": "M barris/sem",
    },
    {
        "id": "us_distillate",
        "slug": "united-states/distillate-stocks",
        "nome": "EUA — destilados (diesel/HO)",
        "regiao": "Estados Unidos",
        "fonte": "EIA",
        "unidade": "M barris/sem",
    },
    {
        "id": "us_api_crude",
        "slug": "united-states/api-crude-oil-stock-change",
        "nome": "EUA — petróleo bruto (API, prévia)",
        "regiao": "Estados Unidos",
        "fonte": "API",
        "unidade": "M barris/sem",
    },
]


def _get(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
        return r.read().decode("utf-8", "ignore")


def _meta_desc(html: str) -> str:
    m = re.search(r'id="metaDesc"[^>]*content="([^"]+)"', html)
    return m.group(1) if m else ""


def _parse_week(txt: str) -> str | None:
    m = re.search(r"week ending\s+([^,.]+(?:\d{4})?)", txt, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"\bin\s+([A-Za-z]+\s+\d{1,2}(?:\s+of\s+\d{4})?)", txt)
    return m.group(1).strip() if m else None


def _parse_change_mmbbl(txt: str) -> float | None:
    """Extrai variação semanal em milhões de barris a partir do texto TE/EIA."""
    if not txt or "economic indicators from 196 countries" in txt.lower():
        return None
    # padrão EIA: decreased/increased by 4.45million barrels
    m = re.search(
        r"(decreased|increased|rose|fell|dropped|declined|climbed|built|drew)\s+by\s*"
        r"(-?[0-9.,]+)\s*(million|thousand)\s*barrels?",
        txt,
        re.I,
    )
    if m:
        val = float(m.group(2).replace(",", ""))
        neg_words = ("decreased", "fell", "dropped", "declined", "drew")
        if m.group(1).lower() in neg_words:
            val = -abs(val)
        if m.group(3).lower().startswith("thousand"):
            val /= 1000.0
        return round(val, 3)
    # distillate: increased to 796 Thousand Barrels ... from -2228
    m2 = re.search(
        r"(increased|decreased)\s+to\s+(-?[0-9.,]+)\s*(Thousand|Million)\s+Barrels?\s+in\s+[^f]+from\s+(-?[0-9.,]+)",
        txt,
        re.I,
    )
    if m2:
        cur = float(m2.group(2).replace(",", ""))
        prev = float(m2.group(4).replace(",", ""))
        chg = cur - prev
        if m2.group(3).lower().startswith("thousand"):
            chg /= 1000.0
        return round(chg, 3)
    return None


def _leitura_variacao(mmbbl: float | None) -> str:
    if mmbbl is None:
        return "Dado indisponível"
    if mmbbl < -0.5:
        return "Queda forte de estoque (draw) — oferta apertada, altista para Brent/WTI"
    if mmbbl < 0:
        return "Queda de estoque — leve pressão de alta no petróleo"
    if mmbbl > 0.5:
        return "Alta forte de estoque (build) — mais oferta, pressão de baixa"
    if mmbbl > 0:
        return "Alta de estoque — leve pressão de baixa"
    return "Estável na semana"


def _fetch_te_series(spec: dict) -> dict:
    url = f"https://tradingeconomics.com/{spec['slug']}"
    try:
        html = _get(url)
        meta = _meta_desc(html)
        chg = _parse_change_mmbbl(meta)
        sem = _parse_week(meta)
        return {
            **spec,
            "variacao_mmbbl": chg,
            "semana_ref": sem,
            "leitura": _leitura_variacao(chg),
            "tag": "oficial" if spec["fonte"] == "EIA" else "preview",
            "atualizado": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:  # noqa: BLE001
        return {**spec, "erro": str(e), "variacao_mmbbl": None, "leitura": "Indisponível"}


def _global_context(us_crude: dict | None) -> dict:
    """Panorama global (OECD/IEA) — contexto mensal + leitura cruzada com EUA."""
    oecd = {
        "nome": "OECD — estoques comerciais de petróleo",
        "regiao": "OCDE (38 países)",
        "fonte": "IEA Oil Market Report / EIA STEO",
        "frequencia": "mensal (~6 sem defasagem)",
        "unidade": "milhões barris",
        "nota": (
            "Estimativa agregada IEA/EIA: estoques comerciais OECD são referência global "
            "para OPEC+ e preço do Brent. Abaixo da média 5 anos = mercado mais apertado."
        ),
        "referencia": {
            "nivel_tipico_oecd_mmbbl": 2700,
            "media_5a_relacao": "próximo da média sazonal",
            "dias_suprimento_oecd": 60,
        },
        "tag": "curado/mensal",
    }
    us = us_crude or {}
    chg = us.get("variacao_mmbbl")
    if chg is not None and chg < -2:
        oecd["leitura"] = "EUA com draw relevante — reforça narrativa de mercado mais apertado globalmente."
        oecd["sinal"] = "altista"
    elif chg is not None and chg > 2:
        oecd["leitura"] = "EUA com build relevante — alivia tightness global de curto prazo."
        oecd["sinal"] = "baixista"
    else:
        oecd["leitura"] = "EUA estável/moderado — acompanhar relatório mensal IEA para confirmação OECD."
        oecd["sinal"] = "neutro"
    return oecd


def _resumo(weekly: list[dict], oecd: dict) -> str:
    us = next((x for x in weekly if x.get("id") == "us_crude"), {})
    chg = us.get("variacao_mmbbl")
    if chg is None:
        return "Estoques EUA indisponíveis; use relatório EIA semanal (quarta-feira) como referência."
    sinal = "draw" if chg < 0 else ("build" if chg > 0 else "estável")
    return (
        f"EUA: variação semanal de estoque bruto {chg:+.2f} M barris ({sinal}). "
        f"OECD: {oecd.get('leitura', '')}"
    )


def build_oil_inventories() -> dict:
    weekly = [_fetch_te_series(s) for s in TE_WEEKLY]
    us_crude = next((x for x in weekly if x.get("id") == "us_crude"), None)
    oecd = _global_context(us_crude)
    # Sinal composto para petroleiras
    scores = [x["variacao_mmbbl"] for x in weekly if x.get("id") in ("us_crude", "us_gasoline", "us_distillate") and x.get("variacao_mmbbl") is not None]
    comp = round(-sum(scores) / len(scores), 2) if scores else 0  # draw = positivo p/ preço
    return {
        "atualizado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fonte": "EIA/API semanal (via TradingEconomics) + contexto OECD/IEA",
        "resumo": _resumo(weekly, oecd),
        "sinal_petroleo": comp,
        "sinal_label": "altista" if comp > 0.3 else ("baixista" if comp < -0.3 else "neutro"),
        "semanal": weekly,
        "global": oecd,
        "glossario": {
            "draw": "Queda de estoque — demanda > oferta na semana",
            "build": "Alta de estoque — oferta > demanda na semana",
            "mmbbl": "Milhões de barris (1 M barris ≈ 159 mil m³)",
        },
    }


def us_crude_change() -> dict:
    """Compatível com live_server.get_inventory()."""
    row = _fetch_te_series(TE_WEEKLY[0])
    return {
        "change_mmbbl": row.get("variacao_mmbbl"),
        "semana": row.get("semana_ref"),
        "fonte": row.get("fonte", "EIA"),
    }


def main() -> None:
    out = build_oil_inventories()
    path = ROOT / "oil_inventories.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    us = next(x for x in out["semanal"] if x["id"] == "us_crude")
    print(f"[OK] {path} · EUA crude {us.get('variacao_mmbbl')} M barris · {out['sinal_label']}")


if __name__ == "__main__":
    main()
