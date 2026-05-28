#!/usr/bin/env python3
"""Re-coleta normas Planalto da pasta AGU com encoding correto → backup separado.

Grava em data/legislacao_agu_recollection/ (não sobrescreve data/legislacao_agu/).

Uso:
  python3 scripts/recollect_agu_planalto_legislacao.py
  python3 scripts/recollect_agu_planalto_legislacao.py --all-planalto
  python3 scripts/recollect_agu_planalto_legislacao.py --include-lexml
  python3 scripts/recollect_agu_planalto_legislacao.py --init-git
  AGU_LEGIS_BACKUP_ROOT=/caminho/backup python3 scripts/recollect_agu_planalto_legislacao.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from naintegra_lex_agent.agu_recollect import (  # noqa: E402
    DEFAULT_BACKUP_ROOT,
    load_source_records,
    needs_planalto_recollection,
    run_recollection,
)

DEFAULT_SOURCE = ROOT / "data" / "legislacao_agu"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-coleta Planalto (ISO-8859-1) em repositório de backup separado"
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(os.environ.get("AGU_LEGIS_SOURCE_DIR", str(DEFAULT_SOURCE))),
        help="JSONL originais (padrão: data/legislacao_agu)",
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        default=Path(os.environ.get("AGU_LEGIS_BACKUP_ROOT", str(ROOT / DEFAULT_BACKUP_ROOT))),
        help="Pasta de backup (padrão: data/legislacao_agu_recollection)",
    )
    parser.add_argument(
        "--all-planalto",
        action="store_true",
        help="Re-coleta todos os Planalto (não só os com encoding corrompido)",
    )
    parser.add_argument(
        "--include-lexml",
        action="store_true",
        help="Copia também registros LexML intactos para o mesmo JSONL de backup",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Máximo de normas Planalto a buscar (debug)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.35,
        help="Intervalo entre requisições ao Planalto (segundos)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lista o que seria re-coletado, sem baixar",
    )
    parser.add_argument(
        "--init-git",
        action="store_true",
        help="Executa git init no backup-root (repositório distinto para versionar)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Roda verify_legislacao_correspondence.py no JSONL gerado",
    )
    args = parser.parse_args()

    source_dir = args.source_dir.expanduser().resolve()
    backup_root = args.backup_root.expanduser().resolve()

    if not source_dir.is_dir():
        print(f"[ERRO] Pasta origem inexistente: {source_dir}", file=sys.stderr)
        return 1

    if args.init_git:
        backup_root.mkdir(parents=True, exist_ok=True)
        git_dir = backup_root / ".git"
        if not git_dir.exists():
            subprocess.run(["git", "init"], cwd=backup_root, check=True)
            print(f"[OK] git init → {backup_root}")
        else:
            print(f"[INFO] Já é repositório git: {backup_root}")

    records = load_source_records(source_dir)
    only_corrupt = not args.all_planalto
    candidates = [
        r
        for r in records.values()
        if "planalto.gov.br" in str(r.get("url") or "").lower()
        and (not only_corrupt or needs_planalto_recollection(r))
    ]

    print(f"Origem: {source_dir} ({len(records)} URL(s) únicas)")
    print(f"Backup: {backup_root}")
    print(f"Candidatos Planalto: {len(candidates)}")
    if only_corrupt:
        print("  (somente com encoding corrompido U+FFFD)")

    if args.dry_run:
        for rec in candidates[:20]:
            print(f"  - {rec.get('title')} → {rec.get('url')}")
        if len(candidates) > 20:
            print(f"  … e mais {len(candidates) - 20}")
        return 0

    out_jsonl, report = run_recollection(
        source_dir=source_dir,
        backup_root=backup_root,
        only_corrupt=only_corrupt,
        include_lexml_copy=args.include_lexml,
        delay_s=args.delay,
        limit=args.limit,
    )

    print(f"\n=== Re-coleta concluída ===")
    print(f"Run: {report.run_id}")
    print(f"  OK: {report.fetched_ok}")
    print(f"  Falhas: {report.failed}")
    print(f"  Ignorados: {report.skipped}")
    if args.include_lexml:
        print(f"  LexML copiados: {report.copied_lexml}")
    print(f"JSONL: {out_jsonl}")
    print(f"Atalho: {backup_root / 'latest.jsonl'}")

    if args.verify and out_jsonl.is_file() and out_jsonl.stat().st_size > 0:
        verify_script = ROOT / "scripts" / "verify_legislacao_correspondence.py"
        run_dir = out_jsonl.parent
        print(f"\n==> Verificação em {run_dir}")
        rc = subprocess.call(
            [
                sys.executable,
                str(verify_script),
                "--input-dir",
                str(run_dir),
                "--json-out",
                str(run_dir / "correspondence_report.json"),
            ],
            cwd=str(ROOT),
        )
        if rc != 0:
            print("[AVISO] Verificação reportou problemas", file=sys.stderr)

    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
