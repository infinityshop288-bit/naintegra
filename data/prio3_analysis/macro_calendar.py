"""Agenda macro futura + Focus BCB (expectativas Selic/IPCA) + fatos CVM sobre juros."""
from __future__ import annotations

import json
import re
import ssl
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    CTX = ssl._create_unverified_context()

UA = {"User-Agent": "Mozilla/5.0 (research; prio3-analysis)"}

COPOM_2026 = [
    ("2026-01-28", "2026-01-29"),
    ("2026-03-17", "2026-03-18"),
    ("2026-05-05", "2026-05-06"),
    ("2026-06-16", "2026-06-17"),
    ("2026-08-04", "2026-08-05"),
    ("2026-09-16", "2026-09-17"),
    ("2026-11-03", "2026-11-04"),
    ("2026-12-08", "2026-12-09"),
]

FOMC_2026 = [
    "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
]

JUROS_KW = re.compile(
    r"SELIC|COPOM|TAXA DE JUROS|JUROS BASIC|FOCUS|IPCA|INFLA[CÇ][AÃ]O|"
    r"MONET[AÁ]RIA|FED FUNDS|FOMC|BANCO CENTRAL|BCB",
    re.I,
)


def _get_json(url: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _olinda(endpoint: str, top: int = 8) -> list[dict]:
    url = (
        "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
        f"{endpoint}?$top={top}&$orderby=Data%20desc&$format=json"
    )
    try:
        data = _get_json(url)
        return data.get("value") or []
    except Exception:  # noqa: BLE001
        return []


def focus_selic() -> dict:
    rows = _olinda("ExpectativasMercadoSelic", 12)
    out = []
    for r in rows:
        out.append({
            "data_coleta": r.get("Data"),
            "reuniao": r.get("Reuniao"),
            "mediana": r.get("Mediana"),
            "minimo": r.get("Minimo"),
            "maximo": r.get("Maximo"),
        })
    return {"atual": out[0] if out else {}, "serie": out[:6], "fonte": "BCB Focus", "tag": "oficial"}


def focus_ipca() -> dict:
    rows = _olinda("ExpectativasMercadoInflacao12Meses", 8)
    out = [{"data_coleta": r.get("Data"), "referencia": r.get("Indicador"), "mediana": r.get("Mediana")} for r in rows]
    return {"atual": out[0] if out else {}, "serie": out[:4], "fonte": "BCB Focus", "tag": "oficial"}


def _ipca_release_dates(start: date, n_months: int = 4) -> list[dict]:
    ev = []
    y, m = start.year, start.month
    for _ in range(n_months):
        d = date(y, m, 12)
        ev.append({
            "data": d.isoformat(),
            "evento": f"Divulgação IPCA {m:02d}/{y} (est.)",
            "tipo": "inflacao",
            "impacto": "Surpresa inflacionária move expectativa de Selic e FIIs/varejo.",
            "tag": "calendario",
        })
        m += 1
        if m > 12:
            m = 1
            y += 1
    return ev


def agenda_eventos(hoje: date | None = None) -> list[dict]:
    hoje = hoje or date.today()
    ev = []
    for ini, fim in COPOM_2026:
        if date.fromisoformat(fim) >= hoje:
            ev.append({
                "data": fim,
                "data_inicio": ini,
                "evento": "Copom — decisão da Selic",
                "tipo": "juros_br",
                "impacto": "Principal driver para FIIs, bancos, varejo e construção.",
                "tag": "oficial",
                "fonte": "BCB",
            })
    for d in FOMC_2026:
        if date.fromisoformat(d) >= hoje:
            ev.append({
                "data": d,
                "evento": "FOMC (Fed) — decisão de juros EUA",
                "tipo": "juros_us",
                "impacto": "Juro americano alto fortalece USD e drena fluxo de emergentes.",
                "tag": "oficial",
                "fonte": "Fed",
            })
    ev.extend(_ipca_release_dates(hoje))
    ev.sort(key=lambda x: x["data"])
    return [e for e in ev if date.fromisoformat(e["data"]) >= hoje][:12]


def fatos_juros_cvm(ipe_df) -> list[dict]:
    if ipe_df is None or ipe_df.empty:
        return []
    cutoff = (date.today() - timedelta(days=180)).isoformat()
    fr = ipe_df[ipe_df["Categoria"].str.contains("Fato Relevante", case=False, na=False)].copy()
    fr = fr[fr["Data_Entrega"] >= cutoff]
    fr = fr[fr["Assunto"].astype(str).str.contains(JUROS_KW, na=False)]
    fr = fr.sort_values("Data_Entrega", ascending=False)
    out, seen = [], set()
    for _, r in fr.head(40).iterrows():
        assunto = re.sub(r"\s+", " ", str(r.get("Assunto") or "")).strip()
        key = assunto[:80].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "data": str(r["Data_Entrega"])[:10],
            "empresa": str(r.get("Nome_Companhia") or "")[:60],
            "assunto": assunto[:200],
            "link": r.get("Link_Download") or "",
            "tipo": "fato_relevante_juros",
        })
        if len(out) >= 15:
            break
    return out


def build_macro_extras(ipe_df=None) -> dict:
    fs = focus_selic()
    fi = focus_ipca()
    agenda = agenda_eventos()
    fatos = fatos_juros_cvm(ipe_df) if ipe_df is not None else []
    prox_copom = next((e for e in agenda if e["tipo"] == "juros_br"), None)
    selic_med = fs.get("atual", {}).get("mediana")
    leitura = (
        f"Focus mediana Selic {selic_med}% "
        f"({'próx. Copom ' + prox_copom['data'] if prox_copom else 'sem Copom próximo'}). "
        f"{len(fatos)} fatos CVM sobre juros nos últimos 6 meses."
    )
    return {
        "focus_selic": fs,
        "focus_ipca": fi,
        "agenda_macro": agenda,
        "fatos_juros": fatos,
        "leitura_juros": leitura,
    }
