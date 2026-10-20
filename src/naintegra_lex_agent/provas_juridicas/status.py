"""Status ao vivo da varredura / loop de IA."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .careers import PROVA_CAREERS

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STATUS = ROOT / "web" / "lex" / "data" / "provas_varredura_status.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_atomic(path: Path, payload: dict[str, Any], *, indent: int | None = 2) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ia = acervo = pendente = 0
    sub = obj = sub_ia = obj_ia = 0
    com_disp = com_juris = 0
    carreiras: Counter[str] = Counter()
    for row in rows:
        meta = row.get("meta") or {}
        kind = str(meta.get("elaboracao") or "pendente")
        if kind == "ia" and str(meta.get("resposta_ia") or "").strip():
            ia += 1
        elif kind == "acervo":
            acervo += 1
        else:
            pendente += 1
        if row.get("doc_type") == "questoes_subjetivas":
            sub += 1
            if kind == "ia":
                sub_ia += 1
        else:
            obj += 1
            if kind == "ia":
                obj_ia += 1
        if meta.get("dispositivos"):
            com_disp += 1
        if meta.get("jurisprudencia"):
            com_juris += 1
        for tag in row.get("carreiras_prova") or []:
            carreiras[str(tag)] += 1
    return {
        "catalogo": len(rows),
        "ia": ia,
        "acervo": acervo,
        "pendente": pendente,
        "subjetivas": sub,
        "objetivas": obj,
        "subjetivas_ia": sub_ia,
        "objetivas_ia": obj_ia,
        "com_dispositivo": com_disp,
        "com_juris": com_juris,
        "carreiras": {k: carreiras.get(k, 0) for k in PROVA_CAREERS},
    }


def row_preview(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    meta = row.get("meta") or {}
    org = row.get("organized") or {}
    body = " ".join(str(row.get("body") or "").split())
    title = str(row.get("title") or body)[:160]
    return {
        "id": str(row.get("external_id") or "")[-16:],
        "tipo": row.get("doc_type"),
        "materia": org.get("materia") or "",
        "banca": org.get("banca") or "",
        "ano": org.get("ano"),
        "carreiras": list(row.get("carreiras_prova") or []),
        "titulo": title,
        "elaboracao": meta.get("elaboracao") or "",
    }


def build_status(
    *,
    rows: list[dict[str, Any]],
    running: bool,
    phase: str,
    model: str,
    cycle: int,
    started_at: str,
    message: str,
    current: dict[str, Any] | None = None,
    last: dict[str, Any] | None = None,
    recent: list[dict[str, Any]] | None = None,
    errors: int = 0,
    last_error: str | None = None,
    rate_per_min: float = 0.0,
    eta_minutes: float | None = None,
    done_this_run: int = 0,
) -> dict[str, Any]:
    totals = summarize(rows)
    pending = totals["pendente"] + totals["acervo"]
    return {
        "job": "provas-juridicas",
        "running": running,
        "phase": phase,
        "model": model,
        "cycle": cycle,
        "pid": os.getpid(),
        "started_at": started_at,
        "updated_at": now_iso(),
        "message": message[:2000],
        "totals": totals,
        "fila": pending,
        "current": current,
        "last": last,
        "recent": (recent or [])[-20:],
        "errors": errors,
        "last_error": last_error,
        "rate_per_min": round(rate_per_min, 2),
        "eta_minutes": None if eta_minutes is None else round(eta_minutes, 1),
        "done_this_run": done_this_run,
    }


def write_status(path: Path, payload: dict[str, Any]) -> Path:
    return write_json_atomic(path, payload)
