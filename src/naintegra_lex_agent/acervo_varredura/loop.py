"""Loop infinito: varre Planalto/LEXML e elabora resumos com a Responses API."""

from __future__ import annotations

import logging
import signal
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from naintegra_lex_agent.lexml_client import search_federal_legislation
from naintegra_lex_agent.planalto_legis import fetch_planalto_text
from naintegra_lex_agent.provas_juridicas.codex_client import DEFAULT_MODEL
from naintegra_lex_agent.provas_juridicas.status import now_iso, write_status

from .enrich import resumo_doutrina, resumo_jurisprudencia, resumo_legislacao
from .paths import (
    DESCOBERTAS,
    DOUTRINA_RESUMOS,
    JURIS_RESUMOS,
    LEGIS_BODIES,
    LEGIS_CATALOG,
    LEGIS_SUMMARIES,
    STATE,
    STATUS,
)
from .scan import (
    body_for,
    build_queue,
    catalog_counts,
    excerpt_from_bodies,
    legis_items,
    load_bodies,
    load_json,
    save_json,
    summary_key,
)

logger = logging.getLogger(__name__)


def _load_state() -> dict[str, Any]:
    raw = load_json(STATE, {})
    if not isinstance(raw, dict):
        return {"planalto": {}, "lexml_at": ""}
    raw.setdefault("planalto", {})
    return raw


def _save_state(state: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    save_json(STATE, state)


def _sidecar_put(path, key: str, payload: dict[str, Any]) -> None:
    raw = load_json(path, {})
    items = dict(raw.get("items") or {})
    items[key] = payload
    save_json(
        path,
        {"generated_at": now_iso(), "count": len(items), "items": items},
    )


def _apply_legis_resumo(url: str, titulo: str, secao: str, resumo: str) -> None:
    key = summary_key(url)
    file = load_json(LEGIS_SUMMARIES, {})
    summaries = dict(file.get("summaries") or {})
    summaries[key] = {
        "titulo": titulo,
        "resumo": resumo,
        "secao": secao,
        "url": url,
        "elaboracao": "ia",
        "updated_at": now_iso(),
    }
    listed = [v for v in summaries.values() if isinstance(v, dict)]
    save_json(
        LEGIS_SUMMARIES,
        {"generated_at": now_iso(), "count": len(summaries), "summaries": summaries, "list": listed},
    )
    catalog = load_json(LEGIS_CATALOG, {})
    changed = False
    for doc in catalog.get("documents") or []:
        if summary_key(str(doc.get("url") or doc.get("doc_key") or "")) != key:
            continue
        doc["resumo"] = resumo
        doc.setdefault("meta", {})["resumo_ia"] = True
        changed = True
    if changed:
        catalog["generated_at"] = now_iso()
        save_json(LEGIS_CATALOG, catalog)


def _refresh_planalto(state: dict[str, Any], *, limit: int, min_len: int = 200) -> dict[str, int]:
    stats = {"fetched": 0, "updated": 0, "failed": 0}
    planalto = dict(state.get("planalto") or {})
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    bodies_file = load_json(LEGIS_BODIES, {})
    bodies = dict(bodies_file.get("bodies") or {})
    dirty = False
    for doc in legis_items():
        if stats["fetched"] >= limit:
            break
        url = str(doc.get("url") or "")
        if "planalto.gov.br" not in url.lower():
            continue
        prev = planalto.get(url) or {}
        try:
            prev_at = datetime.fromisoformat(str(prev.get("fetched_at") or "").replace("Z", "+00:00"))
        except ValueError:
            prev_at = None
        if prev_at and prev_at > cutoff and body_for(url, bodies):
            continue
        try:
            result = fetch_planalto_text(url)
        except Exception as exc:
            stats["failed"] += 1
            planalto[url] = {"fetched_at": now_iso(), "ok": False, "error": str(exc)[:200]}
            logger.warning("Planalto falhou %s: %s", url[-40:], exc)
            continue
        stats["fetched"] += 1
        if result.char_count < min_len:
            planalto[url] = {"fetched_at": now_iso(), "ok": False, "error": "texto curto"}
            continue
        old = body_for(url, bodies)
        planalto[url] = {"fetched_at": now_iso(), "ok": True, "hash": result.content_hash}
        if old and result.content_hash == prev.get("hash"):
            continue
        if result.text != old:
            bodies[url] = result.text
            bodies[f"planalto::{url}"] = result.text
            dirty = True
            stats["updated"] += 1
            logger.info("Lei atualizada %s (%s chars)", doc.get("title"), result.char_count)
    if dirty:
        save_json(
            LEGIS_BODIES,
            {"generated_at": now_iso(), "count": len(bodies), "bodies": bodies},
            indent=None,
        )
        load_bodies(force=True)
    state["planalto"] = planalto
    _save_state(state)
    return stats


def _discover_lexml(state: dict[str, Any]) -> list[dict[str, Any]]:
    last = str(state.get("lexml_at") or "")
    if last:
        try:
            prev = datetime.fromisoformat(last.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - prev < timedelta(hours=6):
                return list((load_json(DESCOBERTAS, {}) or {}).get("hits") or [])
        except ValueError:
            pass
    year = date.today().year
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for keyword in (str(year), str(year - 1), "medida provisoria"):
        try:
            found = search_federal_legislation(keyword)
        except Exception as exc:
            logger.warning("LEXML %s: %s", keyword, exc)
            continue
        for hit in found:
            if hit.date and hit.date < date.today() - timedelta(days=45):
                continue
            if hit.urn in seen:
                continue
            seen.add(hit.urn)
            hits.append(hit.as_dict())
        time.sleep(0.3)
    hits.sort(key=lambda h: str(h.get("date") or ""), reverse=True)
    payload = {"generated_at": now_iso(), "count": len(hits), "hits": hits[:80]}
    save_json(DESCOBERTAS, payload)
    state["lexml_at"] = now_iso()
    _save_state(state)
    logger.info("LEXML: %s atos federais recentes", payload["count"])
    return payload["hits"]


def run_loop(
    *,
    model: str | None = None,
    idle_seconds: float = 30.0,
    planalto_per_cycle: int = 8,
) -> None:
    chosen = (model or DEFAULT_MODEL).strip()
    started_at = now_iso()
    stop = False
    cycle = 0
    errors = 0
    last_error: str | None = None
    done_this_run = 0
    recent: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    phase = "varredura"
    message = "Iniciando varredura do acervo…"
    planalto_stats = {"fetched": 0, "updated": 0, "failed": 0}
    descobertas: list[dict[str, Any]] = []

    def _handle(signum: int, _frame: Any) -> None:
        nonlocal stop, phase, message
        stop = True
        phase = "parado"
        message = f"Encerrado por sinal {signum}"

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    def _flush(running: bool = True) -> None:
        counts = catalog_counts()
        write_status(
            STATUS,
            {
                "job": "acervo-lex",
                "running": running and not stop,
                "phase": phase,
                "model": chosen,
                "cycle": cycle,
                "started_at": started_at,
                "updated_at": now_iso(),
                "message": message[:2000],
                "totals": counts,
                "fila": max(
                    0,
                    (counts["legislacao"] - counts["legis_ia"])
                    + (counts["sumulas"] + counts["temas"] - counts["juris_ia"])
                    + (counts["doutrina"] - counts["doutrina_ia"]),
                ),
                "planalto": planalto_stats,
                "descobertas": len(descobertas),
                "current": current,
                "recent": recent[-20:],
                "errors": errors,
                "last_error": last_error,
                "done_this_run": done_this_run,
            },
        )

    _flush()
    state = _load_state()
    while not stop:
        cycle += 1
        phase = "varredura"
        message = f"Ciclo {cycle}: varrendo legislação, jurisprudência e doutrina…"
        current = None
        _flush()
        try:
            descobertas = _discover_lexml(state)
        except Exception as exc:
            errors += 1
            last_error = str(exc)
            logger.warning("LEXML: %s", exc)
        try:
            planalto_stats = _refresh_planalto(state, limit=planalto_per_cycle)
            if planalto_stats["updated"]:
                message = f"Ciclo {cycle}: {planalto_stats['updated']} leis atualizadas no Planalto"
                _flush()
        except Exception as exc:
            errors += 1
            last_error = str(exc)
            logger.warning("Planalto: %s", exc)

        queue = build_queue()
        if not queue:
            phase = "idle"
            message = "Acervo em dia. Aguardando novas normas no LEXML/Planalto…"
            _flush()
            slept = 0.0
            while not stop and slept < idle_seconds:
                time.sleep(min(3.0, idle_seconds - slept))
                slept += 3.0
                _flush()
            continue

        got = False
        for item in queue:
            if stop:
                break
            current = {
                "id": str(item.get("id") or "")[-18:],
                "kind": item["kind"],
                "titulo": item.get("title"),
                "started_at": now_iso(),
            }
            phase = "ia"
            message = f"Elaborando {item['kind']} · {item.get('title')}"
            _flush()
            t0 = time.monotonic()
            try:
                if item["kind"] == "legislacao":
                    texto = excerpt_from_bodies(str(item.get("url") or ""))
                    if len(texto) < 80:
                        raise RuntimeError("sem texto oficial da lei no acervo")
                    data = resumo_legislacao(
                        titulo=item["title"],
                        secao=str(item.get("secao") or ""),
                        texto=texto,
                        model=chosen,
                    )
                    if len(data["resumo"]) < 20:
                        raise RuntimeError("resumo vazio")
                    _apply_legis_resumo(item["url"], data["titulo"], data["secao"], data["resumo"])
                    kind = "ia"
                elif item["kind"] == "jurisprudencia":
                    data = resumo_jurisprudencia(
                        titulo=item["title"],
                        enunciado=str(item.get("texto") or ""),
                        model=chosen,
                    )
                    if len(data["tese"]) < 20:
                        raise RuntimeError("tese vazia")
                    _sidecar_put(
                        JURIS_RESUMOS,
                        item["id"],
                        {**data, "titulo": item["title"], "subtipo": item.get("subtipo"), "elaboracao": "ia", "updated_at": now_iso()},
                    )
                    kind = "ia"
                else:
                    data = resumo_doutrina(
                        titulo=item["title"],
                        corpo=str(item.get("texto") or ""),
                        model=chosen,
                    )
                    if len(data["resumo"]) < 20:
                        raise RuntimeError("resumo vazio")
                    _sidecar_put(
                        DOUTRINA_RESUMOS,
                        item["id"],
                        {**data, "titulo": item["title"], "elaboracao": "ia", "updated_at": now_iso()},
                    )
                    kind = "ia"
                got = True
                done_this_run += 1
            except Exception as exc:
                kind = "erro"
                errors += 1
                last_error = str(exc)
                logger.warning("IA %s falhou: %s", item.get("id"), exc)
            recent.append(
                {
                    "ts": now_iso(),
                    "id": current["id"],
                    "kind": kind,
                    "tipo": item["kind"],
                    "titulo": item.get("title"),
                    "seconds": round(time.monotonic() - t0, 1),
                }
            )
            recent = recent[-20:]
            current = None
            _flush()

        if stop:
            break
        if not got:
            phase = "idle"
            message = "Nenhuma atualização neste ciclo. Nova tentativa em breve…"
            _flush()
            time.sleep(idle_seconds)

    phase = "parado"
    message = message if str(message).startswith("Encerrado") else "Loop encerrado"
    _flush(running=False)
