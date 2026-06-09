"""Pipeline diário: calendário → IA (Ollama) → fila aguardando_aprovacao (sem publicar)."""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from naintegra_meta.ai_providers import ProviderId, resolve_provider_settings
from naintegra_meta.content_package import generate_content_package
from naintegra_meta.content_calendar import slots_from_today
from naintegra_meta.settings import MetaSettings
from naintegra_meta.store import DelegadoStore

logger = logging.getLogger(__name__)
TZ_BR = ZoneInfo("America/Sao_Paulo")
LOCAL_OUTBOX = Path(__file__).resolve().parents[2] / "data" / "delegado" / "outbox"


def _scheduled_iso(slot: dict[str, Any]) -> str | None:
    d = slot.get("date")
    hour = slot.get("publish_hour") or "19:00"
    if not d:
        return None
    try:
        h, m = hour.split(":")[:2]
        dt = datetime(
            int(d[:4]),
            int(d[5:7]),
            int(d[8:10]),
            int(h),
            int(m),
            tzinfo=TZ_BR,
        )
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


def run_content_pipeline(
    *,
    days: int = 1,
    start_date: date | None = None,
    month: str | None = None,
    provider: ProviderId | None = None,
    settings: MetaSettings | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    os.environ.setdefault("DELEGADO_AI_PROVIDER", "ollama")
    cfg = MetaSettings() if settings is None else settings
    active_provider = provider or resolve_provider_settings()["provider"]  # type: ignore[assignment]
    slots = slots_from_today(days=days, month=month, start=start_date)
    if not slots:
        return {"ok": False, "error": "Nenhum slot no calendário para o período", "created": []}

    store = DelegadoStore(cfg)
    created: list[dict[str, Any]] = []
    errors: list[str] = []

    for slot in slots:
        try:
            item = generate_content_package(
                tema=str(slot.get("tema_macro") or "Concurso policial"),
                formato=str(slot.get("formato") or "carrossel"),
                text_provider=active_provider,
                discipline=slot.get("discipline") if isinstance(slot.get("discipline"), str) else None,
                generate_images=True,
                use_ai_images=True,
            )
            item["scheduled_at"] = _scheduled_iso(slot)
            item.setdefault("meta", {})["ai_source"] = item.get("text_source")
            item.setdefault("meta", {})["package_id"] = item.get("package_id")
            item.setdefault("meta", {})["assets"] = item.get("assets")
            if slot.get("requires_review"):
                item["meta"]["requires_review"] = True

            if dry_run:
                created.append(item)
                continue

            saved = None
            queue_row = {
                "titulo": item.get("titulo") or slot.get("tema_macro"),
                "formato": item.get("formato") or slot.get("formato"),
                "legenda": item.get("legenda") or "",
                "hashtags": item.get("hashtags") or [],
                "media_url": (item.get("assets") or [{}])[0].get("url") if item.get("assets") else None,
                "status": item.get("status", "aguardando_aprovacao"),
                "scheduled_at": item.get("scheduled_at"),
                "meta": {
                    **(item.get("meta") or {}),
                    "package_id": item.get("package_id"),
                    "text_source": item.get("text_source"),
                    "assets": item.get("assets"),
                    "slot_id": slot.get("slot_id"),
                    "calendar_date": slot.get("date"),
                },
            }

            if store.configured:
                try:
                    saved = store.upsert_queue_item_service(queue_row)
                except Exception as exc:
                    logger.warning("Supabase fila falhou (%s) — gravando outbox local", exc)
            if saved:
                created.append(saved)
            else:
                LOCAL_OUTBOX.mkdir(parents=True, exist_ok=True)
                out = LOCAL_OUTBOX / f"{slot['date']}_{slot.get('slot_id', 'post')}.json"
                out.write_text(json.dumps(queue_row, ensure_ascii=False, indent=2), encoding="utf-8")
                queue_row["id"] = str(out)
                queue_row["meta"] = {**(queue_row.get("meta") or {}), "outbox_path": str(out)}
                created.append(queue_row)
        except Exception as exc:
            logger.exception("Falha no slot %s", slot.get("date"))
            errors.append(f"{slot.get('date')}: {exc}")

    return {
        "ok": len(errors) == 0,
        "provider": active_provider,
        "dry_run": dry_run,
        "slots_processed": len(slots),
        "created_count": len(created),
        "created": created,
        "errors": errors,
    }
