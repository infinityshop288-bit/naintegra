"""Histórico por ciclo do organize/questions-loop → JSONL + HTML autocontido (evolução análise/organização)."""

from __future__ import annotations

import json
import logging
import platform
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .settings import Settings

logger = logging.getLogger(__name__)

_EVOLUTION_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Evolução · análise &amp; organização · Lex</title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=Lora:wght@600&family=DM+Mono:wght@400&display=swap" rel="stylesheet" />
  <style>
    :root { --bg:#faf8f4; --surface:#fff; --ink:#111008; --muted:#5c574f; --border:#e8e4dc; --gold:#9a6e00; --ok:#15803d; --err:#b91c1c; }
    * { box-sizing: border-box; }
    body { margin:0; font-family:"DM Sans",system-ui,sans-serif; background:var(--bg); color:var(--ink); font-size:15px; line-height:1.5; min-height:100vh; }
    .shell { max-width:1100px; margin:0 auto; padding:1.75rem 1.25rem 3rem; }
    h1 { font-family:Lora,Georgia,serif; font-size:1.45rem; margin:0 0 .35rem; letter-spacing:-.02em; }
    .sub { color:var(--muted); font-size:.92rem; margin:0 0 1.25rem; max-width:72ch; }
    .hint { font-size:.82rem; color:var(--muted); padding:.85rem 1rem; border:1px solid var(--border); border-radius:12px; background:var(--surface); margin-bottom:1.25rem; }
    .hint code { font-family:"DM Mono",monospace; font-size:.78rem; background:var(--bg); padding:.12rem .35rem; border-radius:4px; }
    #chart-wrap { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1rem; margin-bottom:1.25rem; box-shadow:0 1px 3px rgba(17,16,8,.06); }
    #chart-wrap h2 { font-family:Lora,serif; font-size:1rem; margin:0 0 .65rem; }
    svg { width:100%; height:140px; display:block; }
    table { width:100%; border-collapse:collapse; font-size:.88rem; background:var(--surface); border:1px solid var(--border); border-radius:12px; overflow:hidden; box-shadow:0 1px 3px rgba(17,16,8,.06); }
    th, td { padding:.45rem .55rem; text-align:left; border-bottom:1px solid var(--border); }
    th { font-weight:600; background:rgba(154,110,0,.08); font-size:.78rem; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }
    tr:last-child td { border-bottom:none; }
    tr:hover td { background:rgba(154,110,0,.04); }
    .num { font-family:"DM Mono",monospace; text-align:right; }
    .badge { display:inline-block; padding:.12rem .45rem; border-radius:6px; font-size:.75rem; font-weight:600; }
    .badge.ok { background:rgba(21,128,61,.12); color:var(--ok); }
    .badge.bad { background:rgba(185,28,28,.1); color:var(--err); }
    .empty { color:var(--muted); padding:2rem; text-align:center; }
  </style>
</head>
<body>
  <div class="shell">
    <h1>Evolução da análise e organização</h1>
    <p class="sub">Atualizado a cada ciclo do <code>naintegra-organize-loop</code> ou <code>naintegra-questions-loop</code>. Abra este arquivo diretamente ou sirva a raiz com <code>python3 preview/serve_preview.py</code>.</p>
    <div class="hint">Linha do tempo (documentos normalizados por ciclo) e tabela abaixo — mais recentes no topo. Tipos de documento seguem o corpus fundido (legislação, jurisprudência, súmulas, questões).</div>
    <div id="chart-wrap"><h2>Volume por ciclo</h2><div id="chart"></div></div>
    <div id="table-root"></div>
  </div>
  <script>
  const EVOLUTION = EVOLUTION_DATA_PLACEHOLDER;
  const TYPE_ORDER = ["legislacao","jurisprudencia","sumula","questoes_objetivas","questoes_subjetivas"];

  function typeColumns(rows) {
    const s = new Set();
    rows.forEach(r => { if (r.by_type) Object.keys(r.by_type).forEach(k => s.add(k)); });
    const rest = [...s].filter(k => !TYPE_ORDER.includes(k)).sort();
    return [...TYPE_ORDER.filter(k => s.has(k)), ...rest];
  }

  function renderChart(rows) {
    const el = document.getElementById("chart");
    if (!rows.length) { el.innerHTML = '<p class="empty">Sem ciclos registrados ainda.</p>'; return; }
    const vals = rows.map(r => r.error ? 0 : r.n_docs);
    const max = Math.max(...vals, 1);
    const W = 920, H = 120, P = 14;
    const n = vals.length;
    const pts = vals.map((v, i) => {
      const x = P + (n <= 1 ? (W - 2 * P) / 2 : (i / (n - 1)) * (W - 2 * P));
      const y = H - P - (v / max) * (H - 2 * P);
      return x + "," + y;
    }).join(" ");
    const gold = "#9a6e00";
    el.innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">' +
      '<polyline fill="none" stroke="' + gold + '" stroke-width="2.5" points="' + pts + '" />' +
      vals.map((v, i) => {
        const x = P + (n <= 1 ? (W - 2 * P) / 2 : (i / (n - 1)) * (W - 2 * P));
        const y = H - P - (v / max) * (H - 2 * P);
        return '<circle cx="' + x + '" cy="' + y + '" r="4" fill="' + gold + '" />';
      }).join("") + '</svg>';
  }

  function renderTable(rows) {
    const root = document.getElementById("table-root");
    if (!rows.length) { root.innerHTML = '<p class="empty">Nenhum ciclo gravado em organize_evolution.jsonl.</p>'; return; }
    const cols = typeColumns(rows);
    const sorted = rows.slice().reverse();
    let thead = "<tr><th>Ciclo</th><th>Loop</th><th>Quando</th><th class='num'>Total</th>";
    cols.forEach(c => { thead += "<th class='num'>" + c.replace(/_/g," ") + "</th>"; });
    thead += "<th>Estado</th></tr>";
    let body = "";
    sorted.forEach(r => {
      body += "<tr><td>" + r.cycle + "</td><td>" + (r.loop || "—") + "</td><td>" + r.ts + "</td><td class='num'>" + r.n_docs + "</td>";
      cols.forEach(c => {
        const v = (r.by_type && r.by_type[c]) || 0;
        body += "<td class='num'>" + v + "</td>";
      });
      const ok = !r.error;
      body += "<td>" + (ok ? "<span class='badge ok'>OK</span>" : "<span class='badge bad' title='" + String(r.error).replace(/'/g,"&#39;") + "'>Erro</span>") + "</td></tr>";
    });
    root.innerHTML = "<table><thead>" + thead + "</thead><tbody>" + body + "</tbody></table>";
  }

  renderChart(EVOLUTION);
  renderTable(EVOLUTION);
  </script>
</body>
</html>
"""


def _count_by_type(rows: list[dict[str, Any]]) -> dict[str, int]:
    c = Counter()
    for r in rows:
        c[str(r.get("doc_type") or "?")] += 1
    return dict(sorted(c.items()))


def append_organize_evolution_record(
    settings: Settings,
    *,
    loop_name: str,
    cycle: int,
    rows: list[dict[str, Any]],
    batch_id: str,
    error: str | None = None,
) -> None:
    if not settings.preview_evolution_enabled:
        return
    path = settings.preview_evolution_jsonl_path
    path.parent.mkdir(parents=True, exist_ok=True)
    rec: dict[str, Any] = {
        "loop": loop_name,
        "cycle": cycle,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "batch_id": batch_id,
        "n_docs": len(rows),
        "by_type": _count_by_type(rows),
        "error": error,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def render_evolution_preview_html(settings: Settings, *, max_records: int = 500) -> None:
    if not settings.preview_evolution_enabled:
        return
    path = settings.preview_evolution_jsonl_path
    records: list[dict[str, Any]] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines[-max_records:]:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Linha inválida em %s — ignorada", path)

    blob = json.dumps(records, ensure_ascii=False)
    blob = blob.replace("<", "\\u003c")
    html = _EVOLUTION_HTML_TEMPLATE.replace("EVOLUTION_DATA_PLACEHOLDER", blob)
    out = settings.preview_evolution_html_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def refresh_organize_preview_after_cycle(
    settings: Settings,
    *,
    loop_name: str,
    cycle: int,
    rows: list[dict[str, Any]],
    error: str | None,
) -> None:
    batch_id = (settings.organized_batch_id or "latest").strip() or "latest"
    append_organize_evolution_record(
        settings,
        loop_name=loop_name,
        cycle=cycle,
        rows=rows,
        batch_id=batch_id,
        error=error,
    )
    render_evolution_preview_html(settings)
    logger.info(
        "Preview evolução atualizado — %s",
        settings.preview_evolution_html_path.resolve(),
    )


def completion_note_skip_reason(
    settings: Settings,
    *,
    interrupted_by_signal: bool,
    last_cycle_row_count: int | None,
    last_cycle_failed: bool,
    cycles_executed: int,
) -> str | None:
    """Motivo para **não** abrir «terminei»; ``None`` = abrir bloco de notas."""

    if not settings.preview_open_note_on_exit:
        return "LEX_AGENT_PREVIEW_OPEN_NOTE_ON_EXIT=false"
    if cycles_executed < 1:
        return "nenhum ciclo executado"
    if interrupted_by_signal:
        return (
            "interrupção por sinal (Ctrl+C ou SIGTERM); "
            "a análise/organização do material pode estar incompleta"
        )
    if last_cycle_failed:
        return "último ciclo falhou — material não foi totalmente analisado/organizado"
    if last_cycle_row_count is None:
        return "estado do último ciclo desconhecido"
    cap = settings.max_records_per_cycle
    if last_cycle_row_count >= cap:
        return (
            f"último ciclo normalizou {last_cycle_row_count} documentos "
            f"(≥ LEX_AGENT_MAX_RECORDS_PER_CYCLE={cap}); "
            "pode haver material pendente neste ciclo — rode outra volta até ficar abaixo do limite"
        )
    return None


def maybe_open_terminei_completion_note(
    settings: Settings,
    *,
    interrupted_by_signal: bool,
    last_cycle_row_count: int | None,
    last_cycle_failed: bool,
    cycles_executed: int,
) -> None:
    skip = completion_note_skip_reason(
        settings,
        interrupted_by_signal=interrupted_by_signal,
        last_cycle_row_count=last_cycle_row_count,
        last_cycle_failed=last_cycle_failed,
        cycles_executed=cycles_executed,
    )
    if skip:
        logger.info("Bloco de notas «terminei» omitido: %s", skip)
        return
    write_terminei_note_and_open(settings)


def write_terminei_note_and_open(settings: Settings) -> None:
    note = settings.preview_completion_note_path
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("terminei\n", encoding="utf-8")
    resolved = str(note.resolve())
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", "-e", resolved], check=False)
        elif system == "Windows":
            subprocess.run(["notepad", resolved], check=False)
        else:
            subprocess.run(["xdg-open", resolved], check=False)
        logger.info("Bloco de notas aberto: %s", resolved)
    except Exception as exc:
        logger.warning("Não foi possível abrir o bloco de notas (%s): %s", resolved, exc)
