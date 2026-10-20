from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WEB_DATA = ROOT / "web" / "lex" / "data"

LEGIS_CATALOG = WEB_DATA / "legis_catalog.json"
LEGIS_BODIES = WEB_DATA / "legis_bodies.json"
LEGIS_SUMMARIES = WEB_DATA / "legis_summaries.json"
SUMULAS_CATALOG = WEB_DATA / "sumulas_catalog.json"
TEMAS_CATALOG = WEB_DATA / "temas_catalog.json"
DOUTRINA_CATALOG = WEB_DATA / "doutrina_catalog.json"
JURIS_RESUMOS = WEB_DATA / "juris_resumos.json"
DOUTRINA_RESUMOS = WEB_DATA / "doutrina_resumos.json"
DESCOBERTAS = WEB_DATA / "acervo_descobertas.json"
STATUS = WEB_DATA / "acervo_varredura_status.json"
STATE = ROOT / "data" / "acervo_varredura_state.json"
