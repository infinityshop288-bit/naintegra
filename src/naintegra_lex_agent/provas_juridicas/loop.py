"""Loop infinito: varre o banco, elabora com a Responses API e grava status ao vivo."""

from __future__ import annotations

import json
import logging
import signal
import time
from pathlib import Path
from typing import Any

from .ai_answers import finalize_answer
from .codex_client import DEFAULT_MODEL
from .scan import DEFAULT_OUT, DEFAULT_SRC, _already_ia, load_catalog, scan_rows, write_catalog
from .status import DEFAULT_STATUS, build_status, now_iso, row_preview, write_status

logger = logging.getLogger(__name__)


def merge_new_rows(rows: list[dict[str, Any]], src: Path) -> int:
    if not src.is_file():
        return 0
    raw = json.loads(src.read_text(encoding="utf-8"))
    fresh = scan_rows(list(raw.get("documents") or []))
    known = {str(row.get("external_id") or "") for row in rows}
    added = 0
    for row in fresh:
        eid = str(row.get("external_id") or "")
        if not eid or eid in known:
            continue
        rows.append(row)
        known.add(eid)
        added += 1
    return added


def pending_indices(rows: list[dict[str, Any]]) -> list[int]:
    order = list(range(len(rows)))
    order.sort(key=lambda i: 0 if rows[i].get("doc_type") == "questoes_subjetivas" else 1)
    return [i for i in order if not _already_ia(rows[i])]


def run_loop(
    *,
    src: Path = DEFAULT_SRC,
    dest: Path = DEFAULT_OUT,
    status_path: Path = DEFAULT_STATUS,
    model: str | None = None,
    idle_seconds: float = 20.0,
) -> None:
    chosen = (model or DEFAULT_MODEL).strip()
    started_at = now_iso()
    stop = False
    cycle = 0
    errors = 0
    last_error: str | None = None
    done_this_run = 0
    durations: list[float] = []
    recent: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    last: dict[str, Any] | None = None
    phase = "varredura"
    message = "Iniciando varredura…"

    def _handle(signum: int, _frame: Any) -> None:
        nonlocal stop, phase, message
        stop = True
        phase = "parado"
        message = f"Encerrado por sinal {signum}"
        logger.info(message)

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    if dest.is_file():
        rows = load_catalog(dest)
        logger.info("Loop retomando %s questões", len(rows))
    else:
        raw = json.loads(src.read_text(encoding="utf-8"))
        rows = scan_rows(list(raw.get("documents") or []))
        write_catalog(dest, rows)
        logger.info("Loop varreu %s questões", len(rows))

    def _rate() -> float:
        if not durations:
            return 0.0
        sample = durations[-30:]
        avg = sum(sample) / len(sample)
        return 60.0 / avg if avg > 0 else 0.0

    def _eta() -> float | None:
        pending = sum(1 for row in rows if not _already_ia(row))
        rate = _rate()
        if pending <= 0 or rate <= 0:
            return 0.0 if pending <= 0 else None
        return pending / rate

    def _flush(running: bool = True) -> None:
        write_status(
            status_path,
            build_status(
                rows=rows,
                running=running and not stop,
                phase=phase,
                model=chosen,
                cycle=cycle,
                started_at=started_at,
                message=message,
                current=current,
                last=last,
                recent=recent,
                errors=errors,
                last_error=last_error,
                rate_per_min=_rate(),
                eta_minutes=_eta(),
                done_this_run=done_this_run,
            ),
        )

    _flush()
    while not stop:
        cycle += 1
        phase = "varredura"
        message = f"Ciclo {cycle}: varrendo o banco…"
        current = None
        _flush()
        try:
            added = merge_new_rows(rows, src)
        except Exception as exc:
            errors += 1
            last_error = str(exc)
            logger.warning("Varredura falhou: %s", exc)
            added = 0
        if added:
            write_catalog(dest, rows)
            message = f"Ciclo {cycle}: +{added} questões novas"
            logger.info(message)
            _flush()

        pending = pending_indices(rows)
        if not pending:
            phase = "idle"
            message = "Catálogo em dia. Aguardando novas questões…"
            current = None
            _flush()
            slept = 0.0
            while not stop and slept < idle_seconds:
                time.sleep(min(2.0, idle_seconds - slept))
                slept += 2.0
                _flush()
            continue

        got_ia = False
        for idx in pending:
            if stop:
                break
            row = rows[idx]
            current = row_preview(row)
            if current:
                current["started_at"] = now_iso()
            phase = "ia"
            tipo = "discursiva" if row.get("doc_type") == "questoes_subjetivas" else "objetiva"
            message = f"Elaborando {tipo} · {(current or {}).get('materia') or 'sem matéria'}"
            _flush()
            t0 = time.monotonic()
            try:
                text, kind = finalize_answer(row, use_ai=True, model=chosen)
            except Exception as exc:
                text, kind = "", "erro"
                last_error = str(exc)
                logger.warning("IA falhou: %s", exc)
            elapsed = time.monotonic() - t0
            durations.append(elapsed)
            row.setdefault("meta", {})
            if text:
                row["meta"]["resposta_ia"] = text
            row["meta"]["elaboracao"] = kind if text else "erro"
            write_catalog(dest, rows)
            event = {
                "ts": now_iso(),
                **(row_preview(row) or {}),
                "kind": kind,
                "seconds": round(elapsed, 1),
            }
            last = event
            recent.append(event)
            recent = recent[-20:]
            if kind == "ia":
                done_this_run += 1
                got_ia = True
                logger.info("IA ok %s ciclo=%s fila=%s", event.get("id"), cycle, len(pending_indices(rows)))
            else:
                errors += 1
                last_error = last_error or f"elaboração={kind}"
            current = None
            _flush()

        if stop:
            break
        if not got_ia:
            phase = "idle"
            message = "Nenhuma resposta nova neste ciclo. Nova tentativa em breve…"
            _flush()
            time.sleep(idle_seconds)

    phase = "parado"
    message = message if message.startswith("Encerrado") else "Loop encerrado"
    current = None
    _flush(running=False)
