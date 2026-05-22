from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from ..ingest import iter_records_from_file
from .html_review import build_review_html
from .normalize import (
    flatten_alternativas,
    is_wrong_question,
    pick_answer_user,
    pick_disciplina,
    pick_enunciado,
    pick_gabarito,
    pick_source_id,
    record_hints_qconcurso_source,
    stem_key,
)
from .settings import QConcursoStudySettings, load_qc_study_settings
from .study_ai import bulk_study, run_study_for_consolidated

logger = logging.getLogger(__name__)


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)s %(message)s",
    )


def _iter_inbox_records(inbox: Path, glob_pat: str) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    if not inbox.exists():
        logger.warning("Inbox inexistente: %s", inbox)
        return rows
    for path in sorted(inbox.glob(glob_pat)):
        if path.is_file():
            for rec in iter_records_from_file(path):
                rows.append((path.name, rec))
    for path in sorted(inbox.glob("*.json")):
        if path.is_file():
            for rec in iter_records_from_file(path):
                rows.append((path.name, rec))
    return rows


def consolidate_from_inbox(
    inbox: Path,
    glob_pat: str,
    *,
    only_qconcurso_hint: bool = False,
) -> list[dict[str, Any]]:
    wrong_by_stem: dict[str, dict[str, Any]] = {}

    for fname, raw in _iter_inbox_records(inbox, glob_pat):
        if only_qconcurso_hint and not record_hints_qconcurso_source(raw):
            continue
        if is_wrong_question(raw) is not True:
            continue

        enunciado = pick_enunciado(raw)
        alt = flatten_alternativas(
            raw.get("alternativas")
            or raw.get("opcoes")
            or raw.get("choices")
            or raw.get("itens")
        )
        if not enunciado or not alt:
            logger.debug("Ignorado (sem enunciado ou alternativas): %s", fname)
            continue

        sk = stem_key(enunciado, alt)
        gab = pick_gabarito(raw)
        usr = pick_answer_user(raw)
        gid = pick_source_id(raw) or f"{fname}:{raw.get('_source_line','?')}"

        if sk not in wrong_by_stem:
            wrong_by_stem[sk] = {
                "stem_key": sk,
                "disciplina": pick_disciplina(raw),
                "enunciado": enunciado,
                "alternativas": alt,
                "merged_source_ids": [gid],
                "sample_inbox_files": [fname],
                "_gabarito_letter_hidden": gab,
                "_user_wrong_letter_hidden": usr,
            }
            continue

        base = wrong_by_stem[sk]
        base["merged_source_ids"].append(gid)
        if fname not in base.setdefault("sample_inbox_files", []):
            base["sample_inbox_files"].append(fname)
        if gab and base.get("_gabarito_letter_hidden") and base["_gabarito_letter_hidden"] != gab:
            logger.warning("Conflito de gabarito no mesmo stem (%s…) — primeiro valor preservado.", sk[:14])
        elif gab and not base.get("_gabarito_letter_hidden"):
            base["_gabarito_letter_hidden"] = gab
        base["_user_wrong_letter_hidden"] = base.get("_user_wrong_letter_hidden") or usr
        if not base.get("disciplina"):
            base["disciplina"] = pick_disciplina(raw)

    consolidated = sorted(wrong_by_stem.values(), key=lambda x: x["stem_key"])
    logger.info("%s temas únicos consolidados.", len(consolidated))
    return consolidated


def write_consolidated(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "# QConcursos (qconcursos.com) / crawl — erros consolidados por stem (JSONL)."
    lines = [header, *[json.dumps(r, ensure_ascii=False) for r in rows]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_consolidated(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(json.loads(s))
    return out


def cmd_ingest(
    *,
    inbox: Path,
    glob_pat: str,
    out_path: Path,
    only_hint: bool,
) -> int:
    rows = consolidate_from_inbox(inbox, glob_pat, only_qconcurso_hint=only_hint)
    write_consolidated(out_path, rows)
    logger.info("Consolidado: %s", out_path.resolve())
    return 0


def cmd_study(
    settings: QConcursoStudySettings,
    consolidated: Path,
    *,
    force: bool,
    max_batches: int | None,
    stem_only: str | None,
) -> int:
    rows = read_consolidated(consolidated)
    if not rows:
        logger.error("Sem dados em %s (rode ingest).", consolidated)
        return 1
    if stem_only:
        for row in rows:
            if row.get("stem_key") == stem_only:
                run_study_for_consolidated(settings, row, force=force)
                return 0
        logger.error("stem_key não encontrado.")
        return 2
    bulk_study(settings, rows, force=force, max_new=max_batches)
    return 0


def cmd_html(settings: QConcursoStudySettings, out_override: Path | None) -> int:
    if out_override:
        settings.review_html_path = Path(out_override)
    built = build_review_html(settings)
    print(str(built.resolve()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Extrai erros do crawl (qconcursos.com) → estudo jurídico por IA → HTML. "
            "Subcomandos playwright-*: sessão Chromium e coleta JSON da rede (opcional)."
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(pa: argparse.ArgumentParser, with_inbox: bool) -> None:
        if with_inbox:
            pa.add_argument("--inbox", default=None)
            pa.add_argument("--glob", default=None)
            pa.add_argument(
                "--only-qconcurso-hint",
                "--only-qconcursos-hint",
                dest="only_qconcurso_hint",
                action="store_true",
                help=(
                    'Só registros cuja JSON serializada mencione qconcursos.com / qconcurso.com '
                    '(ou legacy qconcursos .br)'
                ),
            )
        pa.add_argument(
            "--consolidated",
            default=None,
            help="JSONL consolidado (padrão: QC_STUDY_CONSOLIDATED_PATH)",
        )

    ingest_p = sub.add_parser("ingest", help="Gera consolidated.jsonl a partir da inbox")
    add_common(ingest_p, True)
    ingest_p.add_argument("--out", default=None)

    study_p = sub.add_parser("study", help="Gera texto IA na pasta studies/")
    add_common(study_p, False)
    study_p.add_argument("--force", action="store_true")
    study_p.add_argument("--max-batches", type=int, default=None)

    one_p = sub.add_parser("study-one", help="Uma entrada por stem_key")
    add_common(one_p, False)
    one_p.add_argument("--stem", required=True)
    one_p.add_argument("--force", action="store_true")

    html_p = sub.add_parser("html", help="Um HTML só com todas as revisões IA")
    add_common(html_p, False)
    html_p.add_argument("--review-html-out", dest="review_out", default=None)

    run_p = sub.add_parser("run", help="Encadeia ingest → study → html")
    add_common(run_p, True)
    run_p.add_argument("--out", default=None)
    run_p.add_argument("--force", action="store_true")
    run_p.add_argument("--max-batches", type=int, default=None)

    pws = sub.add_parser(
        "playwright-save-state",
        help="Abre Chromium: faça login no QConcurso e pressione Enter para gravar sessão.",
    )
    pws.add_argument("--state-out", default=None, help="Destino JSON Playwright (cookies/localStorage)")
    pws.add_argument("--start-url", default=None, help="URL inicial (default: QC_STUDY_QCONCURSO_BASE_URL)")

    pwo = sub.add_parser(
        "playwright-observe",
        help="Lista respostas JSON da rede (URLs e chaves de topo) para calibrar filtros.",
    )
    pwo.add_argument("--state", dest="pw_state", default=None)
    pwo.add_argument("--start-url", default=None)
    pwo.add_argument("--seconds", type=float, default=45.0)
    pwo.add_argument("--headed", action="store_true")
    pwo.add_argument("--url-contains", default="", dest="url_contains")

    pwh = sub.add_parser(
        "playwright-harvest",
        help="Navega, intercepta JSON e grava questões em JSONL (erradas ou todas com gabarito).",
    )
    pwh.add_argument("--state", dest="pw_state", default=None)
    pwh.add_argument("--start-url", default=None)
    pwh.add_argument("--seconds", type=float, default=60.0)
    pwh.add_argument("--headed", action="store_true")
    pwh.add_argument("--url-contains", default="", dest="url_contains")
    pwh.add_argument("--out", default=None)
    pwh.add_argument("--append", action="store_true", help="Concatena ao JSONL sem truncar.")
    pwh.add_argument(
        "--wrong-only",
        action="store_true",
        help="Só persiste questões inferidas como erradas (modo legado consolidado de erros).",
    )
    pwh.add_argument(
        "--emit-unknown-wrong",
        action="store_true",
        help="Inclui questão sem flag de erro na API (marca acertou=false e _assumed_wrong_no_flag).",
    )
    pwh.add_argument(
        "--emit-all-with-gabarito",
        action="store_true",
        help="Força modo Lex (objetivas com gabarito + discursivas); é o padrão deste comando.",
    )

    return p


def main() -> None:
    settings = load_qc_study_settings()
    parser = build_parser()
    args = parser.parse_args()
    configure_logging("INFO")

    consolidated_arg = getattr(args, "consolidated", None)
    consolidated_default = Path(consolidated_arg) if consolidated_arg else Path(settings.consolidated_path)

    try:
        if args.command == "ingest":
            inbox = Path(args.inbox or settings.qconcurso_inbox_path)
            glob_pat = args.glob or settings.qconcurso_glob
            out_path = Path(args.out) if args.out else Path(settings.consolidated_path)
            sys.exit(
                cmd_ingest(inbox=inbox, glob_pat=glob_pat, out_path=out_path, only_hint=args.only_qconcurso_hint)
            )

        if args.command == "study":
            sys.exit(
                cmd_study(
                    settings,
                    consolidated_default,
                    force=args.force,
                    max_batches=args.max_batches,
                    stem_only=None,
                )
            )

        if args.command == "study-one":
            sys.exit(
                cmd_study(
                    settings,
                    consolidated_default,
                    force=args.force,
                    max_batches=None,
                    stem_only=args.stem,
                )
            )

        if args.command == "html":
            ov = Path(args.review_out) if args.review_out else None
            sys.exit(cmd_html(settings, ov))

        if args.command == "run":
            inbox = Path(args.inbox or settings.qconcurso_inbox_path)
            glob_pat = args.glob or settings.qconcurso_glob
            out_path = Path(args.out) if args.out else Path(settings.consolidated_path)
            if cmd_ingest(
                inbox=inbox,
                glob_pat=glob_pat,
                out_path=out_path,
                only_hint=args.only_qconcurso_hint,
            ):
                sys.exit(1)

            consolidated_for_study = out_path if args.consolidated is None else Path(args.consolidated)
            if cmd_study(
                settings,
                consolidated_for_study,
                force=args.force,
                max_batches=args.max_batches,
                stem_only=None,
            ):
                sys.exit(1)
            ro = getattr(args, "review_out", None)
            ov = Path(ro) if ro else None
            if cmd_html(settings, ov):
                sys.exit(1)
            sys.exit(0)

        if args.command == "playwright-save-state":
            from .playwright_capture import cmd_playwright_save_state

            st_out = Path(args.state_out) if args.state_out else Path(settings.playwright_storage_state_path)
            start_u = (args.start_url or settings.qconcurso_base_url).strip()
            sys.exit(cmd_playwright_save_state(out_state=st_out, start_url=start_u))

        if args.command == "playwright-observe":
            from . import playwright_capture

            cand = Path(args.pw_state) if args.pw_state else Path(settings.playwright_storage_state_path)
            st_exist = cand if cand.is_file() else None

            sys.exit(
                playwright_capture.cmd_playwright_observe(
                    settings=settings,
                    state_path=st_exist,
                    start_url=(args.start_url or settings.qconcurso_base_url).strip(),
                    headed=bool(args.headed),
                    seconds=float(args.seconds),
                    url_substring=str(args.url_contains or ""),
                )
            )

        if args.command == "playwright-harvest":
            from . import playwright_capture

            cand = Path(args.pw_state) if args.pw_state else Path(settings.playwright_storage_state_path)
            st_exist = cand if cand.is_file() else None

            src = settings.qconcurso_base_url.rstrip("/") + "/"
            harvest_mode = "wrong_only" if args.wrong_only else "all_with_gabarito"
            if args.emit_all_with_gabarito:
                harvest_mode = "all_with_gabarito"
            sys.exit(
                playwright_capture.cmd_playwright_harvest(
                    settings=settings,
                    state_path=st_exist,
                    start_url=(args.start_url or settings.qconcurso_base_url).strip(),
                    headed=bool(args.headed),
                    seconds=float(args.seconds),
                    url_substring=str(args.url_contains or ""),
                    out_arg=args.out,
                    emit_if_wrong_unknown=bool(args.emit_unknown_wrong),
                    harvest_emit_mode=harvest_mode,
                    source_note=src,
                    append=bool(args.append),
                )[0]
            )

    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
