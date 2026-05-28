#!/usr/bin/env python3
"""Verifica correspondência entre título, URL, tags, ementa e texto das normas coletadas.

Uso:
  python3 scripts/verify_legislacao_correspondence.py
  python3 scripts/verify_legislacao_correspondence.py --input-dir data/legislacao_agu
  python3 scripts/verify_legislacao_correspondence.py --json-out data/reports/legislacao_correspondence.json
  python3 scripts/verify_legislacao_correspondence.py --fail-on error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from naintegra_lex_agent.legis_correspondence import (  # noqa: E402
    summarize_reports,
    verify_all,
)

DEFAULT_INPUT = ROOT / "data" / "legislacao_agu"
DEFAULT_CATALOG = ROOT / "web" / "lex" / "data" / "legis_catalog.json"
DEFAULT_REPORT = ROOT / "data" / "reports" / "legislacao_correspondence.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica se título, URL, tags e texto de cada norma correspondem entre si."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT,
        help="Pasta com legislacao_agu_*.jsonl",
    )
    parser.add_argument(
        "--include-catalog",
        action="store_true",
        help="Inclui também entradas de web/lex/data/legis_catalog.json",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Caminho do catálogo (com --include-catalog)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"Relatório JSON (padrão: {DEFAULT_REPORT.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--no-json-out",
        action="store_true",
        help="Não grava relatório JSON em disco",
    )
    parser.add_argument(
        "--fail-on",
        choices=("error", "warn", "never"),
        default="error",
        help="Código de saída 1 se houver falhas do nível indicado",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Lista cada norma com problema",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    if not input_dir.is_dir():
        print(f"[ERRO] Pasta não encontrada: {input_dir}", file=sys.stderr)
        return 1

    catalog = None
    if args.include_catalog:
        catalog = args.catalog or DEFAULT_CATALOG
        if not catalog.is_file():
            print(f"[AVISO] Catálogo não encontrado: {catalog}", file=sys.stderr)

    reports = verify_all(input_dir=input_dir, catalog_path=catalog)
    summary = summarize_reports(reports)

    print("=== Verificação de correspondência (lei × descrição) ===")
    print(f"Pasta: {input_dir}")
    print(f"Normas analisadas: {summary['total']}")
    print(f"  OK: {summary['ok']}")
    print(f"  Com falha: {summary['failed']}")
    print(f"  Codificação corrompida (verificação limitada): {summary['skipped_encoding']}")
    if summary["issues_by_code"]:
        print("Ocorrências por tipo:")
        for code, n in summary["issues_by_code"].items():
            print(f"  {code}: {n}")

    failed = [r for r in reports if not r.ok]
    if args.verbose and failed:
        print("\n--- Detalhes ---")
        for r in failed:
            print(f"\n• {r.title}")
            print(f"  {r.url}")
            if r.identities:
                print(f"  Identidades: {r.identities}")
            for issue in r.issues:
                print(f"  [{issue.severity}] {issue.code}: {issue.message}")

    if args.no_json_out:
        json_out = ""
    else:
        json_out = str(args.json_out).strip()
    if json_out:
        out_path = Path(json_out).expanduser()
        if out_path.name:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "summary": summary,
                "reports": [r.to_dict() for r in reports],
            }
            out_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"\nRelatório JSON → {out_path}")

    if args.fail_on == "never":
        return 0
    if args.fail_on == "error":
        has_error = any(
            not r.ok and any(i.severity == "error" for i in r.issues) for r in reports
        )
        return 1 if has_error else 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
