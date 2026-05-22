"""Sessão Playwright para salvar estado e colher JSON útil da rede em JSONL."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable

from .import_adapters import HarvestEmitMode, extract_inbox_records_from_json_payload
from .settings import QConcursoStudySettings

logger = logging.getLogger(__name__)


def _response_source_note(response_url: str, fallback: str) -> str:
    """Origem da captura: domínio da própria resposta HTTP (multi-site)."""

    try:
        from urllib.parse import urlparse

        p = urlparse(response_url)
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}/"
    except Exception:
        pass
    fb = (fallback or "").strip()
    return fb if fb else "https://unknown-origin/"


def _maybe_parse_json(body: bytes) -> Any | None:
    if not body or len(body) > 15_000_000:
        return None
    try:
        txt = body.decode("utf-8")
    except UnicodeDecodeError:
        try:
            txt = body.decode("utf-8", errors="replace")
        except Exception:
            return None
    stripped = txt.lstrip()
    if stripped.startswith("\ufeff"):
        stripped = stripped.lstrip("\ufeff").lstrip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def cmd_playwright_save_state(
    *,
    out_state: Path,
    start_url: str,
    message: str = "Faça login em qconcursos.com. Depois volte ao terminal e pressione Enter.",
) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error(
            "Pacote playwright ausente. Instale com: pip install 'naintegra-lex-agent[playwright]' "
            "e depois: playwright install chromium",
        )
        return 127

    out_state.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "%s Ao fechar esta janela sem Enter, pressione Ctrl+C aqui.", message.replace("\n", " ")
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as exc:
            logger.warning(
                "Falha ao abrir %s (%s). Na janela do Chromium, digite o endereço manualmente, "
                "faça login no site e volte ao terminal para pressionar Enter.",
                start_url,
                exc,
            )
        input()
        context.storage_state(path=str(out_state))
        context.close()
        browser.close()
    logger.info("Estado salvo em %s", out_state.resolve())
    return 0


def cmd_playwright_observe(
    *,
    settings: QConcursoStudySettings,
    state_path: Path | None,
    start_url: str,
    headed: bool,
    seconds: float,
    url_substring: str,
) -> int:
    """Lista respostas JSON (URL + forma das chaves) para ajudar a calibrar o harvest."""

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Instale playwright (extra [playwright]) e rode playwright install chromium")
        return 127

    snippets: list[str] = []

    def on_response(resp: Any) -> None:
        try:
            fu = getattr(resp, "url", "") or ""
        except Exception:
            return
        if url_substring and url_substring not in fu:
            return

        try:
            body = resp.body()
        except Exception:
            return

        payload = _maybe_parse_json(body)
        if payload is None:
            return

        top_keys: str
        if isinstance(payload, dict):
            kk = sorted(str(k) for k in payload.keys())
            top_keys = ", ".join(kk[:18]) + ("…" if len(kk) > 18 else "")
        elif isinstance(payload, list):
            top_keys = f"list[{len(payload)}]"
        else:
            top_keys = type(payload).__name__

        snippets.append(f"{resp.status}\t{fu[:180]}\t{top_keys}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        kw: dict[str, Any] = {}
        if state_path and state_path.is_file():
            kw["storage_state"] = str(state_path)
        context = browser.new_context(**kw)
        page = context.new_page()
        page.on("response", on_response)
        page.goto(start_url, wait_until="domcontentloaded", timeout=90_000)
        time.sleep(seconds)
        context.close()
        browser.close()

    for line in sorted(set(snippets))[:250]:
        print(line)
    print(f"-- total snippets {len(set(snippets))} --")
    return 0


def resolve_harvest_jsonl(settings: QConcursoStudySettings, out_arg: str | None) -> Path:
    inbox = Path(settings.qconcurso_inbox_path)
    inbox.mkdir(parents=True, exist_ok=True)
    trimmed = (out_arg or "").strip()
    if not trimmed:
        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        return (inbox / f"playwright_network_{ts}.jsonl").resolve()

    cand = Path(trimmed).expanduser()
    if len(cand.parts) > 1 or cand.is_absolute():
        target = cand.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    return (inbox / cand.name).resolve()


def cmd_playwright_harvest(
    *,
    settings: QConcursoStudySettings,
    state_path: Path | None,
    start_url: str,
    headed: bool,
    seconds: float,
    url_substring: str,
    out_arg: str | None,
    emit_if_wrong_unknown: bool,
    harvest_emit_mode: HarvestEmitMode = "all_with_gabarito",
    source_note: str,
    append: bool = False,
) -> tuple[int, int]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Instale playwright (extra [playwright]) e playwright install chromium")
        return 127, 0

    out_dest = resolve_harvest_jsonl(settings, out_arg)
    out_dest.parent.mkdir(parents=True, exist_ok=True)
    if not append:
        out_dest.write_text("", encoding="utf-8")

    dedupe: set[str] = set()
    n_written = 0

    def append_records(records: list[dict[str, Any]]) -> None:
        nonlocal n_written
        if not records:
            return
        with out_dest.open("a", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_written += 1

    def on_response(resp: Any) -> None:
        """Captura corpos JSON mesmo sem Content-Type ``application/json`` (APIs com tipo vazio ou genérico)."""

        try:
            fu = getattr(resp, "url", "") or ""
        except Exception:
            return
        if url_substring and url_substring not in fu:
            return
        try:
            body = resp.body()
        except Exception:
            return
        payload = _maybe_parse_json(body)
        if payload is None:
            return

        extracted = extract_inbox_records_from_json_payload(
            payload,
            emit_if_wrong_unknown=emit_if_wrong_unknown,
            harvest_emit_mode=harvest_emit_mode,
            dedupe_keys_seen=dedupe,
            source_url_note=_response_source_note(fu, source_note),
        )
        if extracted:
            logger.info("%s registros novos ← %s", len(extracted), fu[:140])
            append_records(extracted)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        kw: dict[str, Any] = {}
        if state_path and Path(state_path).is_file():
            kw["storage_state"] = str(state_path)
            logger.info("Sessão: %s", state_path.resolve())
        else:
            logger.warning(
                "Sem arquivo de estado; abra apenas páginas públicas ou passe --headed e faça login na mão."
            )

        context = browser.new_context(**kw)
        page = context.new_page()
        page.on("response", on_response)
        page.goto(start_url, wait_until="domcontentloaded", timeout=90_000)
        time.sleep(seconds)
        if headed:
            st_out = settings.playwright_storage_state_path
            st_out.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(st_out))
            logger.info("Estado da sessão gravado em %s (harvest headed)", st_out.resolve())
        context.close()
        browser.close()

    logger.info("Gravados %s registros únicos → %s", n_written, out_dest.resolve())
    return 0, n_written


def cmd_playwright_harvest_url_plan(
    *,
    settings: QConcursoStudySettings,
    state_path: Path | None,
    url_tag_pairs: list[tuple[str, dict[str, Any]]],
    headed: bool,
    seconds_per_url: float,
    url_substring: str,
    emit_if_wrong_unknown: bool,
    harvest_emit_mode: HarvestEmitMode,
    partition_sink: Callable[[list[dict[str, Any]]], None] | None,
    source_note: str = "https://exam-scrape.naintegra/",
) -> tuple[int, int]:
    """Navega sequencialmente por URLs com etiquetas (banca/cargo/fonte) e grava via ``partition_sink``.

    Útil para rotacionar buscas agregadas (QConcurso, Techconcursos, etc.) sem reiniciar o browser.
    """

    if not url_tag_pairs:
        return 0, 0

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Instale playwright (extra [playwright]) e rode playwright install chromium")
        return 127, 0

    dedupe: set[str] = set()
    n_written = 0
    current_tags: dict[str, Any] = {}

    def sink(rows: list[dict[str, Any]]) -> None:
        nonlocal n_written
        if not rows:
            return
        tagged = [{**r, **current_tags} for r in rows]
        n_written += len(tagged)
        if partition_sink is not None:
            partition_sink(tagged)

    def on_response(resp: Any) -> None:
        try:
            fu = getattr(resp, "url", "") or ""
        except Exception:
            return
        if url_substring and url_substring not in fu:
            return
        try:
            body = resp.body()
        except Exception:
            return
        payload = _maybe_parse_json(body)
        if payload is None:
            return

        extracted = extract_inbox_records_from_json_payload(
            payload,
            emit_if_wrong_unknown=emit_if_wrong_unknown,
            harvest_emit_mode=harvest_emit_mode,
            dedupe_keys_seen=dedupe,
            source_url_note=_response_source_note(fu, source_note),
        )
        if extracted:
            logger.info("%s registros novos ← %s", len(extracted), fu[:140])
            sink(extracted)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        kw: dict[str, Any] = {}
        if state_path and Path(state_path).is_file():
            kw["storage_state"] = str(state_path)
            logger.info("Sessão: %s", state_path.resolve())
        else:
            logger.warning(
                "Sem arquivo de estado; login pode falhar nos agregadores — grave estado com playwright-save-state."
            )

        context = browser.new_context(**kw)
        page = context.new_page()
        page.on("response", on_response)

        for url, tags in url_tag_pairs:
            current_tags = tags
            logger.info(
                "Harvest URL → %s [%s · %s · %s]",
                url[:160],
                tags.get("banca"),
                tags.get("cargo_alvo") or tags.get("cargo"),
                tags.get("fonte"),
            )
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            except Exception:
                logger.exception("Falha ao abrir URL (continua próximo par)")
                continue
            time.sleep(float(seconds_per_url))

        context.close()
        browser.close()

    logger.info("Harvest multi-URL: %s registros gravados (partição externa)", n_written)
    return 0, n_written
