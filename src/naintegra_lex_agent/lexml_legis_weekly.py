"""Pipeline semanal: LEXML → crawl_inbox → promoção Planalto no Supabase (Lex)."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .legis_promote import (
    export_legis_offline_bundle,
    export_legis_summaries,
    list_catalog_rows,
    load_json_state,
    promote_or_remove_law,
    save_json_state,
    supabase_credentials_from_env,
    utc_now,
)
from .lexml_client import (
    discover_hits_for_law_numbers,
    hit_from_crawl_record,
    iter_crawl_jsonl,
    merge_hits,
    run_external_crawl_command,
    write_crawl_inbox,
)
from .lexml_impact import (
    analyze_impact,
    catalog_urls_for_law_numbers,
    crawl_record_from_hit,
    extract_law_numbers,
    law_number_in_url,
    normalize_law_number,
)
from .planalto_legis import discovered_catalog_rows, merge_catalog
from .settings import Settings, load_settings

logger = logging.getLogger("naintegra_lex_agent.lexml_legis_weekly")

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "data" / "lexml_weekly_state.json"
PROMOTE_STATE_PATH = ROOT / "data" / "legis_update_state.json"


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def since_date_from_state(state: dict[str, Any], lookback_days: int) -> date:
    raw = state.get("last_run")
    if raw:
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (dt - timedelta(days=1)).date()
        except ValueError:
            pass
    return date.today() - timedelta(days=max(1, lookback_days))


def platform_law_numbers(catalog: list[dict[str, str]]) -> list[str]:
    nums: set[str] = set()
    for item in catalog:
        url = str(item.get("url") or "")
        n = law_number_in_url(url)
        if n:
            nums.add(normalize_law_number(n))
        for t in extract_law_numbers(str(item.get("titulo") or "")):
            nums.add(normalize_law_number(t))
    return sorted(nums)


def hits_affecting_platform(
    hits: list[Any],
    platform_nums: set[str],
) -> list[tuple[Any, Any]]:
    out: list[tuple[Any, Any]] = []
    for hit in hits:
        blob = f"{hit.title}\n{hit.ementa}"
        mentioned = {normalize_law_number(n) for n in extract_law_numbers(blob)}
        affected = mentioned & platform_nums
        report = analyze_impact(
            title=hit.title,
            ementa=hit.ementa,
            urn=hit.urn,
            url=hit.url,
        )
        report_targets = {normalize_law_number(n) for n in report.affected_law_numbers()}
        affected |= report_targets & platform_nums
        if not affected:
            continue
        if report.actions:
            report.actions[0].target_law_numbers = sorted(affected)
        out.append((hit, report))
    return out


def catalog_targets_for_reports(
    catalog: list[dict[str, str]],
    impacted: list[tuple[Any, Any]],
) -> list[dict[str, str]]:
    nums: set[str] = set()
    for _, report in impacted:
        nums.update(normalize_law_number(n) for n in report.affected_law_numbers())
    if not nums:
        return []
    return catalog_urls_for_law_numbers(catalog, nums)


def load_recent_crawl_hits(settings: Settings) -> list[Any]:
    inbox = settings.crawl_inbox_path.resolve()
    paths = sorted(inbox.glob("lexml*.jsonl"))
    paths.extend(sorted(inbox.glob("*lexml*.jsonl")))
    records = iter_crawl_jsonl(paths[-20:])
    hits = []
    for rec in records:
        h = hit_from_crawl_record(rec)
        if h:
            hits.append(h)
    return hits


def run_weekly(
    settings: Settings,
    *,
    dry_run: bool = False,
    force: bool = False,
    no_export: bool = False,
    also_refresh_all: bool = False,
    lookback_days: int | None = None,
    max_searches: int | None = None,
) -> dict[str, Any]:
    sb_url, key = supabase_credentials_from_env()
    if not sb_url or not key:
        if dry_run:
            catalog = merge_catalog()
            logger.warning("Dry-run sem Supabase: catálogo estático Planalto (%s leis).", len(catalog))
        else:
            raise RuntimeError("Defina LEX_AGENT_SUPABASE_URL e LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY.")
    else:
        discovered = discovered_catalog_rows(list_catalog_rows(sb_url, key))
        catalog = merge_catalog(*discovered)

    lookback = lookback_days if lookback_days is not None else settings.lexml_lookback_days
    state = load_json_state(STATE_PATH)
    promote_state = load_json_state(PROMOTE_STATE_PATH)
    docs_state: dict[str, Any] = dict(promote_state.get("documents") or {})
    since = since_date_from_state(state, lookback)

    platform_nums = set(platform_law_numbers(catalog))
    law_nums = platform_law_numbers(catalog)

    crawl_msg = ""
    if settings.lexml_crawl_command.strip():
        code, crawl_msg = run_external_crawl_command(
            settings.lexml_crawl_command,
            timeout=settings.lexml_crawl_timeout_seconds,
        )
        logger.info("LEXML crawl externo: %s", crawl_msg)
        if code not in (0, 124):
            logger.warning("Comando LEXML externo exit=%s", code)

    search_hits = discover_hits_for_law_numbers(
        law_nums,
        since=since,
        sleep_seconds=settings.lexml_search_sleep_seconds,
        max_searches=max_searches,
    )
    crawl_hits = load_recent_crawl_hits(settings)
    all_hits = merge_hits(search_hits, crawl_hits)
    impacted = hits_affecting_platform(all_hits, platform_nums)

    crawl_records = [crawl_record_from_hit(h.as_dict(), rep) for h, rep in impacted]
    inbox_path: Path | None = None
    if crawl_records and not dry_run:
        inbox_path = write_crawl_inbox(settings.crawl_inbox_path, crawl_records)

    targets = catalog_targets_for_reports(catalog, impacted)
    if also_refresh_all:
        targets = catalog

    stats = {
        "since": since.isoformat(),
        "catalog_laws": len(catalog),
        "search_hits": len(search_hits),
        "crawl_hits": len(crawl_hits),
        "impacting_hits": len(impacted),
        "targets": len(targets),
        "updated": 0,
        "removed": 0,
        "skipped": 0,
        "errors": 0,
        "chunks": 0,
    }

    have = None
    if targets and not dry_run and sb_url and key:
        from .norma_chunks import list_catalog_doc_keys

        have = list_catalog_doc_keys(supabase_url=sb_url, supabase_key=key, source="planalto")

    for law in targets:
        titulo = law["titulo"]
        print(f"[PROMOTE] {titulo}")
        if dry_run and not sb_url:
            print("  would_update: dry-run sem Supabase")
            stats["updated"] += 1
            continue
        result = promote_or_remove_law(
            sb_url=sb_url or "",
            key=key or "",
            law=law,
            force=force or also_refresh_all,
            dry_run=dry_run,
            have=have,
            docs_state=docs_state,
            corpus_tag="legislacao_lexml_weekly",
        )
        print(f"  {result.action}: {result.message}")
        if result.action == "updated":
            stats["updated"] += 1
            stats["chunks"] += result.chunks
        elif result.action == "removed":
            stats["removed"] += 1
        elif result.action == "skipped":
            stats["skipped"] += 1
        elif result.action.startswith("would_"):
            stats["updated" if "update" in result.action else "removed"] += 1
        elif result.action == "error":
            stats["errors"] += 1

    if not dry_run and stats["chunks"] and sb_url and key:
        from .norma_chunks import refresh_catalog_mv

        refresh_catalog_mv(supabase_url=sb_url, supabase_key=key)
        if not no_export:
            export_legis_summaries(ROOT)
            export_legis_offline_bundle(ROOT)

    state["last_run"] = utc_now()
    state["since"] = since.isoformat()
    state["stats"] = stats
    state["seen_urns"] = sorted({h.urn for h, _ in impacted})
    if crawl_msg:
        state["external_crawl"] = crawl_msg
    if inbox_path:
        state["inbox_file"] = str(inbox_path)

    promote_state["last_lexml_run"] = utc_now()
    promote_state["documents"] = docs_state
    if not dry_run:
        save_json_state(STATE_PATH, state)
        save_json_state(PROMOTE_STATE_PATH, promote_state)

    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Descobre alterações no LEXML e promove atualizações no NaIntegra Lex",
    )
    parser.add_argument("--dry-run", action="store_true", help="Só descobre e simula promoção")
    parser.add_argument("--force", action="store_true", help="Re-ingere alvos mesmo sem hash novo")
    parser.add_argument("--no-export", action="store_true", help="Não regenera JSON offline do Lex")
    parser.add_argument(
        "--also-refresh-all",
        action="store_true",
        help="Após LEXML, atualiza todo o catálogo Planalto (hash)",
    )
    parser.add_argument("--lookback-days", type=int, default=None, help="Janela se não houver last_run")
    parser.add_argument("--max-searches", type=int, default=None, help="Limite de buscas LEXML por ciclo")
    args = parser.parse_args(argv)

    settings = load_settings()
    _configure_logging(settings.log_level)

    try:
        stats = run_weekly(
            settings,
            dry_run=args.dry_run,
            force=args.force,
            no_export=args.no_export,
            also_refresh_all=args.also_refresh_all,
            lookback_days=args.lookback_days,
            max_searches=args.max_searches,
        )
    except Exception as exc:
        logger.exception("Falha no pipeline LEXML semanal: %s", exc)
        return 1

    print(
        f"\nLEXML semanal: {stats['impacting_hits']} hit(s) relevante(s), "
        f"{stats['targets']} alvo(s), {stats['updated']} atualizada(s), "
        f"{stats['removed']} removida(s), {stats['skipped']} inalterada(s), "
        f"{stats['errors']} erro(s)."
    )
    return 0 if stats["errors"] == 0 else 1


def main_sync() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    raise SystemExit(main())
