"""Loop periódico de scraping com `data/scrape_status.json` para o monitor HTML.

Modos:
  - ``shell``: executa ``LEX_AGENT_SCRAPE_LOOP_SHELL_COMMAND`` (crawler externo, curl, etc.).
  - ``playwright_harvest``: sessão Chromium que grava JSONL no inbox QConcurso (extra ``[playwright]``).
"""

from __future__ import annotations

import json
import logging
import signal
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from .settings import Settings, load_settings

logger = logging.getLogger("naintegra_lex_agent.scrape_loop")


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def write_scrape_status(
    path: Path,
    *,
    job: str,
    done: int,
    total: int,
    message: str,
    exit_code: int | None = None,
    mode: str | None = None,
    records_written: int | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "job": job,
        "done": done,
        "total": total,
        "message": message[:2000],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if exit_code is not None:
        payload["exit_code"] = exit_code
    if mode:
        payload["mode"] = mode
    if records_written is not None:
        payload["records_written"] = records_written
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_scrape_cycle(settings: Settings) -> tuple[int, str, int]:
    """Retorna (exit_code, mensagem, registros gravados no último harvest)."""

    mode = settings.scrape_loop_mode
    if mode == "shell":
        cmd = (settings.scrape_loop_shell_command or "").strip()
        if not cmd:
            return 2, "Comando vazio (LEX_AGENT_SCRAPE_LOOP_SHELL_COMMAND)", 0
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=float(settings.scrape_loop_shell_timeout_seconds),
            )
            tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            if len(tail) > 900:
                tail = tail[-900:]
            msg = f"exit={proc.returncode} {tail}".strip()
            return proc.returncode, msg, 0
        except subprocess.TimeoutExpired:
            return 124, "timeout no comando shell", 0
        except Exception as exc:
            return 1, str(exc), 0

    if mode == "playwright_harvest":
        from .concurso_study.playwright_capture import cmd_playwright_harvest
        from .concurso_study.settings import load_qc_study_settings

        qc = load_qc_study_settings()
        st_path = qc.playwright_storage_state_path
        st_exist = st_path if st_path.is_file() else None
        trimmed_start = (settings.scrape_harvest_start_url or "").strip()
        start_url = trimmed_start or qc.qconcurso_base_url.strip()
        src = qc.qconcurso_base_url.rstrip("/") + "/"
        trimmed_out = (settings.scrape_harvest_out or "").strip()
        out_arg = trimmed_out or None
        code, n_written = cmd_playwright_harvest(
            settings=qc,
            state_path=st_exist,
            start_url=start_url,
            headed=settings.scrape_harvest_headed,
            seconds=float(settings.scrape_harvest_seconds),
            url_substring=(settings.scrape_harvest_url_substring or "").strip(),
            out_arg=out_arg,
            emit_if_wrong_unknown=settings.scrape_harvest_emit_unknown_wrong,
            harvest_emit_mode=settings.scrape_harvest_emit_mode,
            source_note=src,
            append=settings.scrape_harvest_append,
        )
        if code == 0 and n_written == 0:
            logger.info(
                "playwright_harvest: 0 registros neste ciclo — confira login em %s, tempo "
                "LEX_AGENT_SCRAPE_HARVEST_SECONDS=%s e modo LEX_AGENT_SCRAPE_HARVEST_EMIT_MODE=%s "
                "(wrong_only quase não grava se você só acerta).",
                st_path,
                settings.scrape_harvest_seconds,
                settings.scrape_harvest_emit_mode,
            )
        return code, f"playwright_harvest exit={code}", n_written

    return 3, f"modo desconhecido: {mode}", 0


def main_sync() -> None:
    settings = load_settings()
    _configure_logging(settings.log_level)

    if settings.scrape_loop_mode == "off":
        logger.info("LEX_AGENT_SCRAPE_LOOP_MODE=off — encerrando.")
        sys.exit(0)

    stop = threading.Event()

    def _stop(*_: object) -> None:
        logger.info("Encerrando scrape-loop (sinal)...")
        stop.set()

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    cycles = 0
    successes = 0

    logger.info(
        "NaIntegra scrape-loop — modo=%s intervalo=%ss status→%s",
        settings.scrape_loop_mode,
        settings.scrape_loop_interval_seconds,
        settings.scrape_status_path,
    )

    while not stop.is_set():
        cycles += 1
        try:
            code, msg, rec = run_scrape_cycle(settings)
            if code == 0:
                successes += 1
            write_scrape_status(
                settings.scrape_status_path,
                job=settings.scrape_job_name,
                done=successes,
                total=cycles,
                message=msg,
                exit_code=code,
                mode=settings.scrape_loop_mode,
                records_written=rec if rec > 0 else None,
            )
            logger.info(
                "Ciclo %s — exit=%s acumulado_ok=%s/%s records_último=%s",
                cycles,
                code,
                successes,
                cycles,
                rec,
            )
        except Exception:
            logger.exception("Falha no ciclo de scraping")
            write_scrape_status(
                settings.scrape_status_path,
                job=settings.scrape_job_name,
                done=successes,
                total=cycles,
                message="exceção no ciclo (ver logs do agente)",
                exit_code=-1,
                mode=settings.scrape_loop_mode,
            )

        if stop.wait(timeout=float(settings.scrape_loop_interval_seconds)):
            break

    logger.info("scrape-loop encerrado (%s ciclos, %s com exit 0)", cycles, successes)
    sys.exit(0)


def main() -> None:
    main_sync()


if __name__ == "__main__":
    main_sync()
