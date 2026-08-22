"""Scraping dos Fatos Relevantes da PRIO S.A. (ex-PetroRio / ex-HRT).

Fonte oficial: Portal de Dados Abertos da CVM (IPE - Informacoes Periodicas
e Eventuais). Contem TODOS os documentos protocolados por companhias abertas,
inclusive a categoria "Fato Relevante", com link de download do documento.

URL base:
https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_YYYY.csv
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).resolve().parent
CNPJ_PRIO = "10.629.105/0001-68"  # PRIO S.A. (codigo CVM 22187)
YEARS = range(2021, 2027)
BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{y}.zip"

HEADERS = {"User-Agent": "Mozilla/5.0 (research; prio3-analysis)"}


def load_year(year: int) -> pd.DataFrame | None:
    url = BASE.format(y=year)
    print(f"Baixando IPE {year} ...")
    try:
        r = requests.get(url, headers=HEADERS, timeout=90)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"  falhou {year}: {e}")
        return None
    content = r.content
    # alguns anos podem vir zipados
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            name = [n for n in z.namelist() if n.endswith(".csv")][0]
            content = z.read(name)
    for enc in ("latin-1", "utf-8"):
        try:
            df = pd.read_csv(io.BytesIO(content), sep=";", encoding=enc, dtype=str)
            break
        except Exception:  # noqa: BLE001
            df = None
    if df is None:
        print(f"  nao consegui parsear {year}")
        return None
    return df


def main() -> None:
    all_frames = []
    for y in YEARS:
        df = load_year(y)
        if df is not None:
            all_frames.append(df)

    if not all_frames:
        raise SystemExit("Nenhum dado IPE baixado.")

    ipe = pd.concat(all_frames, ignore_index=True)
    ipe.columns = [c.strip() for c in ipe.columns]
    print("Colunas:", list(ipe.columns))

    # Filtra pela PRIO (por CNPJ, robusto a mudancas de razao social)
    cnpj_col = next(c for c in ipe.columns if "CNPJ" in c.upper())
    prio = ipe[ipe[cnpj_col].astype(str).str.strip() == CNPJ_PRIO].copy()
    print(f"Documentos PRIO (todos os tipos): {len(prio)}")

    # Categoria de Fato Relevante
    cat_col = next(c for c in ipe.columns if c.strip().lower() in ("categoria",))
    print("Categorias disponiveis PRIO:", sorted(prio[cat_col].dropna().unique()))
    fatos = prio[prio[cat_col].str.contains("Fato Relevante", case=False, na=False)].copy()

    # Ordena por data
    data_col = next(c for c in fatos.columns if c.strip().lower().startswith("data_"))
    fatos = fatos.sort_values(data_col)

    keep_candidates = [
        "Nome_Companhia", "CNPJ_Companhia", "Categoria", "Tipo",
        "Assunto", "Data_Referencia", "Data_Entrega", "Link_Download",
    ]
    keep = [c for c in keep_candidates if c in fatos.columns]
    fatos_out = fatos[keep].reset_index(drop=True)

    fatos_out.to_csv(OUT / "fatos_relevantes_prio.csv", index=False)
    prio.to_csv(OUT / "todos_documentos_prio.csv", index=False)

    print(f"\nFatos Relevantes PRIO encontrados: {len(fatos_out)}")

    # Resumo por ano
    fatos_out["_ano"] = fatos_out[data_col if data_col in fatos_out else keep[-3]].astype(str).str[:4]
    resumo = fatos_out.groupby("_ano").size().to_dict()
    (OUT / "fatos_resumo.json").write_text(
        json.dumps({"total": len(fatos_out), "por_ano": resumo}, indent=2, ensure_ascii=False)
    )
    print("Por ano:", json.dumps(resumo, ensure_ascii=False))

    # Mostra os assuntos
    subj_col = next((c for c in fatos_out.columns if c.lower() == "assunto"), None)
    if subj_col:
        for _, row in fatos_out.iterrows():
            d = row.get(data_col, "")
            print(f"  {str(d)[:10]} | {str(row.get(subj_col, ''))[:110]}")


if __name__ == "__main__":
    main()
