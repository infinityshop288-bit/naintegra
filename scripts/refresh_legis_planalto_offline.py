#!/usr/bin/env python3
"""Atualiza legis_catalog.json e legis_bodies.json a partir do texto compilado do Planalto.

Regra: para normas alteradoras, o texto vigente está no diploma alterado (compilado no Planalto,
com trechos revogados em ~~...~~). As leis de alteração entram como documentos próprios.

Uso:
  python3 scripts/refresh_legis_planalto_offline.py
  python3 scripts/refresh_legis_planalto_offline.py --url https://.../del2848.htm
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from naintegra_lex_agent.planalto_legis import content_hash, fetch_planalto_text  # noqa: E402

CONAMA_237_URL = "https://conama.mma.gov.br/resolucao-conama-n-237-1997"
CONAMA_237_PDF = (
    "https://conama.mma.gov.br/?id=237&option=com_sisconama&task=arquivo.download"
)

CATALOG = ROOT / "web" / "lex" / "data" / "legis_catalog.json"
BODIES = ROOT / "web" / "lex" / "data" / "legis_bodies.json"
SUMMARIES = ROOT / "web" / "lex" / "data" / "legis_summaries.json"

_meta_path = ROOT / "scripts" / "build_legis_known_meta.py"
_spec = importlib.util.spec_from_file_location("build_legis_known_meta", _meta_path)
meta_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(meta_mod)

KNOWN = meta_mod.KNOWN
match_key = meta_mod.match_key
build_entries = meta_mod.build_entries
patch_catalog = meta_mod.patch_catalog
patch_summaries = meta_mod.patch_summaries
patch_bodies = meta_mod.patch_bodies

# Leis novas (texto autônomo no Planalto)
NEW_LEGIS: list[dict[str, str]] = [
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/lei/l15397.htm",
        "titulo": "Lei 15.397/2026 — Aumento de penas (crimes patrimoniais)",
        "resumo": "Altera o Código Penal para majorar penas de furto, roubo, estelionato e receptação.",
        "secao": "Penal e Processual",
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/lei/l15358.htm",
        "titulo": "Lei 15.358/2026 — Marco Legal do Combate ao Crime Organizado",
        "resumo": "Institui o marco legal anticrime organizado (Lei Raul Jungmann / Antifacção).",
        "secao": "Penal e Processual",
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/l15272.htm",
        "titulo": "Lei 15.272/2025 — Atualizações processuais penais",
        "resumo": "Altera o CPP sobre prisão preventiva, audiência de custódia e coleta de DNA.",
        "secao": "Penal e Processual",
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14193.htm",
        "titulo": "Lei 14.193/2021 — Sociedade Anônima do Futebol",
        "resumo": "Institui a SAF e disciplina a transformação de clubes em sociedades anônimas.",
        "secao": "Civil e Trabalho",
    },
    {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/leis_2001/l10216.htm",
        "titulo": "Lei 10.216/2001 — Reforma Psiquiátrica",
        "resumo": "Dispõe sobre a proteção e os direitos das pessoas portadoras de transtornos mentais.",
        "secao": "Legislação Especial",
    },
]

# Edital MPSP / carreiras jurídicas — diplomas ausentes do acervo offline
MPSP_EDITAL_LEGIS: list[dict[str, str]] = [
    {"url": "https://www.planalto.gov.br/ccivil_03/leis/l8625.htm", "secao": "Constituição e Adm."},
    {"url": "https://www.planalto.gov.br/ccivil_03/leis/l7853.htm", "secao": "Legislação Especial"},
    {"url": "https://www.planalto.gov.br/ccivil_03/leis/l8080.htm", "secao": "Legislação Especial"},
    {"url": "https://www.planalto.gov.br/ccivil_03/leis/l8142.htm", "secao": "Legislação Especial"},
    {"url": "https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2007/lei/l11445.htm", "secao": "Legislação Especial"},
    {"url": "https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2010/lei/l12305.htm", "secao": "Legislação Especial"},
    {"url": "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l13019.htm", "secao": "Legislação Especial"},
    {"url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2017/lei/l13431.htm", "secao": "Penal e Processual"},
    {"url": "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2019/lei/l13964.htm", "secao": "Penal e Processual"},
    {"url": "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14119.htm", "secao": "Legislação Especial"},
    {"url": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/l14811.htm", "secao": "Penal e Processual"},
    {"url": "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp135.htm", "secao": "Constituição e Adm."},
    {"url": "https://www.planalto.gov.br/ccivil_03/decreto/D0678.htm", "secao": "Legislação Especial"},
    {"url": "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2004/decreto/d5051.htm", "secao": "Legislação Especial"},
    {"url": "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/decreto/D10932.htm", "secao": "Legislação Especial"},
    {"url": "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/decreto/D11129.htm", "secao": "Constituição e Adm."},
]

# Diplomas alterados — texto compilado no Planalto reflete vigência (~~revogado~~)
REFRESH_COMPILED: list[str] = [
    "https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848.htm",  # CP ← 15.397, 15.358
    "https://www.planalto.gov.br/ccivil_03/decreto-lei/del3689.htm",  # CPP ← 15.272, 15.358
    "http://www.planalto.gov.br/ccivil_03/leis/l7210.htm",  # LEP ← 15.358
    "http://www.planalto.gov.br/ccivil_03/leis/l8072.htm",  # Hediondos ← 15.358
    "http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12850.htm",  # Org. criminosa
    "http://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11343.htm",  # Drogas
    "http://www.planalto.gov.br/ccivil_03/leis/2003/l10.826.htm",  # Desarmamento
]


def normalize_url(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("http://"):
        return "https://" + u[7:]
    return u


def url_aliases(url: str) -> set[str]:
    u = normalize_url(url)
    out = {u, u.replace("https://", "http://")}
    return {x for x in out if x}


def catalog_index(docs: list[dict]) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for doc in docs:
        for key in ("url", "doc_key"):
            raw = doc.get(key) or ""
            for alias in url_aliases(raw):
                idx[alias] = doc
    return idx


def titulo_for_url(url: str, fallback: str = "") -> str:
    key = match_key(url)
    if key and key in KNOWN:
        return KNOWN[key][0]
    entries = build_entries()
    if key and key in entries:
        return entries[key]["titulo"]
    return fallback or url


def make_catalog_doc(spec: dict[str, str], fetched_hash: str) -> dict:
    url = normalize_url(spec["url"])
    titulo = spec.get("titulo") or titulo_for_url(url)
    secao = spec.get("secao") or "Penal e Processual"
    resumo = spec.get("resumo") or ""
    corpus = spec.get("corpus") or "legislacao_planalto_refresh"
    return {
        "external_id": f"planalto::{url}",
        "doc_type": "legislacao",
        "source_system": "planalto",
        "doc_key": url,
        "title": titulo,
        "resumo": resumo,
        "url": url,
        "meta": {
            "corpus": corpus,
            "titulo": titulo,
            "resumo": resumo,
            "doc_key": url,
            "doc_type": "legislacao",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": fetched_hash,
            "secao_lei_seca": secao,
            "norma_schema_version": 1,
        },
        "organized": {
            "secao_lei_seca": secao,
            "corpus": corpus,
        },
        "chunk_count": None,
    }


def upsert_catalog_doc(docs: list[dict], spec: dict[str, str], fetched_hash: str) -> bool:
    idx = catalog_index(docs)
    url = normalize_url(spec["url"])
    existing = idx.get(url)
    doc = make_catalog_doc(spec, fetched_hash)
    if existing:
        existing.update(doc)
        existing["meta"] = {**(existing.get("meta") or {}), **doc["meta"]}
        existing["organized"] = doc["organized"]
        return False
    docs.append(doc)
    return True


def upsert_summary_list(url: str, titulo: str, resumo: str, secao: str) -> None:
    if not SUMMARIES.exists():
        return
    data = json.loads(SUMMARIES.read_text(encoding="utf-8"))
    path_key = urlparse(url).path.lower()
    summaries = data.setdefault("summaries", {})
    summaries[path_key] = {
        "titulo": titulo,
        "resumo": resumo,
        "secao": secao,
        "url": url,
    }
    lst = data.setdefault("list", [])
    found = False
    for item in lst:
        if normalize_url(item.get("url") or "") == normalize_url(url):
            item["titulo"] = titulo
            item["resumo"] = resumo
            item["secao"] = secao
            item["url"] = url
            found = True
            break
    if not found:
        lst.append({"titulo": titulo, "resumo": resumo, "secao": secao, "url": url})
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    data["count"] = len(lst)
    SUMMARIES.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_conama_237_text() -> str:
    """Baixa PDF oficial do MMA/CONAMA e extrai texto (pymupdf)."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Instale pymupdf para importar Resolução CONAMA 237") from exc

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf_path = Path(tmp.name)
    try:
        subprocess.run(
            [
                "curl",
                "-sL",
                "-A",
                "Mozilla/5.0 (compatible; NaIntegraLex/1.0)",
                "-o",
                str(pdf_path),
                CONAMA_237_PDF,
            ],
            check=True,
            timeout=120,
        )
        doc = fitz.open(str(pdf_path))
        try:
            text = "\n\n".join(page.get_text("text").strip() for page in doc if page.get_text("text").strip())
        finally:
            doc.close()
    finally:
        pdf_path.unlink(missing_ok=True)

    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 2000:
        raise RuntimeError(f"texto CONAMA 237 curto ({len(text)} chars)")
    return text


def upsert_legis_text(
    url: str,
    text: str,
    *,
    titulo: str = "",
    resumo: str = "",
    secao: str = "",
    corpus: str = "legislacao_planalto_refresh",
) -> tuple[bool, str]:
    arts = len(re.findall(r"\bArt\.?\s*\d", text))
    if arts < 1 and len(text) < 400:
        raise RuntimeError(f"texto curto ({len(text)} chars, {arts} arts)")

    catalog_data = json.loads(CATALOG.read_text(encoding="utf-8"))
    docs: list[dict] = catalog_data.get("documents") or []
    idx = catalog_index(docs)

    titulo = titulo or titulo_for_url(url)
    spec = {
        "url": normalize_url(url),
        "titulo": titulo,
        "resumo": resumo,
        "secao": secao,
        "corpus": corpus,
    }
    h = content_hash(text)
    added = upsert_catalog_doc(docs, spec, h)
    catalog_data["documents"] = docs
    catalog_data["count"] = len(docs)
    catalog_data["generated_at"] = datetime.now(timezone.utc).isoformat()
    CATALOG.write_text(json.dumps(catalog_data, ensure_ascii=False, indent=2), encoding="utf-8")

    bodies_data = json.loads(BODIES.read_text(encoding="utf-8"))
    bodies: dict[str, str] = bodies_data.get("bodies") or {}
    body = f"# {titulo}\n\nFonte: {normalize_url(url)}\n\n{text}"
    target = idx.get(normalize_url(url))
    keys = {normalize_url(url), f"planalto::{normalize_url(url)}"}
    if target:
        keys.add(normalize_url(target.get("doc_key") or target.get("url") or url))
        keys.add(target.get("external_id", ""))
    for k in keys:
        if k:
            bodies[k] = body
    bodies_data["bodies"] = bodies
    bodies_data["count"] = len(bodies)
    bodies_data["generated_at"] = datetime.now(timezone.utc).isoformat()
    BODIES.write_text(json.dumps(bodies_data, ensure_ascii=False), encoding="utf-8")

    if resumo or secao:
        upsert_summary_list(
            normalize_url(url),
            titulo,
            resumo or "",
            secao or "Legislação Especial",
        )

    action = "added" if added else "updated"
    return added, f"{action} — {len(text)} chars, ~{arts} arts"


def refresh_url(
    url: str,
    *,
    titulo: str = "",
    resumo: str = "",
    secao: str = "",
) -> tuple[bool, str]:
    planalto_url = url.replace("https://", "http://") if "planalto.gov.br" in url else url
    fetched = fetch_planalto_text(planalto_url)
    return upsert_legis_text(
        url,
        fetched.text,
        titulo=titulo or titulo_for_url(url),
        resumo=resumo,
        secao=secao,
    )


def ingest_conama_237() -> tuple[bool, str]:
    meta = KNOWN["conama237"]
    text = fetch_conama_237_text()
    return upsert_legis_text(
        CONAMA_237_URL,
        text,
        titulo=meta[0],
        resumo=meta[1],
        secao=meta[2],
        corpus="legislacao_conama_mma",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Atualiza legislação offline via Planalto")
    parser.add_argument("--url", action="append", help="URL adicional do Planalto")
    parser.add_argument("--compiled-only", action="store_true", help="Só diplomas compilados alterados")
    parser.add_argument("--new-only", action="store_true", help="Só leis novas")
    parser.add_argument("--conama-237", action="store_true", help="Inclui Resolução CONAMA 237/1997 (MMA)")
    parser.add_argument("--snuc", action="store_true", help="Atualiza Lei 9.985/2000 (SNUC) no Planalto")
    parser.add_argument(
        "--mpsp-edital",
        action="store_true",
        help="Inclui leis do edital MPSP ainda ausentes do acervo offline",
    )
    args = parser.parse_args()

    entries = build_entries()
    patch_catalog(entries)

    explicit = bool(args.url or args.conama_237 or args.snuc or args.mpsp_edital)
    targets: list[tuple[str, dict[str, str] | None]] = []
    if args.mpsp_edital:
        entries = build_entries()
        for spec in MPSP_EDITAL_LEGIS:
            url = normalize_url(spec["url"])
            key = match_key(url)
            meta = entries.get(key or "", {})
            titulo = spec.get("titulo") or meta.get("titulo") or titulo_for_url(url)
            targets.append(
                (
                    url,
                    {
                        "url": url,
                        "titulo": titulo,
                        "resumo": spec.get("resumo") or meta.get("resumo", ""),
                        "secao": spec.get("secao") or meta.get("secao") or "Legislação Especial",
                    },
                )
            )
    if not explicit:
        if not args.compiled_only:
            for spec in NEW_LEGIS:
                targets.append((spec["url"], spec))
        if not args.new_only:
            for url in REFRESH_COMPILED:
                targets.append((url, None))
    for url in args.url or []:
        targets.append((url, None))
    if args.snuc:
        titulo, resumo, secao = KNOWN["l9985"]
        targets.append(
            (
                "https://www.planalto.gov.br/ccivil_03/leis/l9985.htm",
                {
                    "url": "https://www.planalto.gov.br/ccivil_03/leis/l9985.htm",
                    "titulo": titulo,
                    "resumo": resumo,
                    "secao": secao,
                },
            )
        )

    errors = 0
    for url, spec in targets:
        titulo = (spec or {}).get("titulo") or titulo_for_url(url)
        resumo = (spec or {}).get("resumo") or ""
        secao = (spec or {}).get("secao") or ""
        print(f"[FETCH] {titulo}")
        try:
            _, msg = refresh_url(url, titulo=titulo, resumo=resumo, secao=secao)
            print(f"  [OK] {msg}")
        except Exception as exc:
            errors += 1
            print(f"  [ERRO] {exc}", file=sys.stderr)

    if args.conama_237:
        print("[FETCH] Resolução CONAMA 237/1997 — Licenciamento ambiental")
        try:
            _, msg = ingest_conama_237()
            print(f"  [OK] {msg}")
        except Exception as exc:
            errors += 1
            print(f"  [ERRO] {exc}", file=sys.stderr)

    entries = build_entries()
    patch_summaries(entries)
    patch_catalog(entries)
    patch_bodies(entries)
    print(f"\nConcluído com {errors} erro(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
