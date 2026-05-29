#!/usr/bin/env bash
# Supervisão: mantém Ollama + extração CP IURIS 2025 rodando até concluir.
# No macOS, usa caffeinate para impedir repouso do sistema durante a extração.
if [[ "$(uname -s)" == Darwin ]] && command -v caffeinate >/dev/null 2>&1 && [[ -z "${CP_IURIS_CAFFEINATE_ACTIVE:-}" ]]; then
  export CP_IURIS_CAFFEINATE_ACTIVE=1
  exec caffeinate -dims "$0" "$@"
fi

set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO/data/cp_iuris_2025"
LOG="$OUT/watchdog.log"
PID_FILE="$OUT/watchdog.pid"
INTERVAL="${CP_IURIS_WATCHDOG_INTERVAL_SECONDS:-30}"

export PYTHONPATH="$REPO/src"
export CP_IURIS_AI_MODEL="${CP_IURIS_AI_MODEL:-llama3.2:3b}"
export CP_IURIS_CHUNKS_PER_CYCLE="${CP_IURIS_CHUNKS_PER_CYCLE:-16}"
export CP_IURIS_PARALLEL_WORKERS="${CP_IURIS_PARALLEL_WORKERS:-3}"
export CP_IURIS_POLL_INTERVAL_SECONDS="${CP_IURIS_POLL_INTERVAL_SECONDS:-0}"
export CP_IURIS_DELAY_SECONDS="${CP_IURIS_DELAY_SECONDS:-0}"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-3}"

mkdir -p "$OUT"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    log "Watchdog já ativo (PID $old_pid). Nada a fazer."
    exit 0
  fi
fi
echo "$$" >"$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT

ollama_up() {
  curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1
}

ollama_process_running() {
  pgrep -x ollama >/dev/null 2>&1 || pgrep -f "ollama serve" >/dev/null 2>&1
}

extract_running() {
  pgrep -f "extract_cp_iuris_2025_loop.py" >/dev/null 2>&1
}

extraction_done() {
  [[ -f "$OUT/terminei.txt" ]]
}

ensure_ollama() {
  if ollama_up; then
    return 0
  fi
  if ! ollama_process_running; then
    log "Ollama offline — iniciando ollama serve (OLLAMA_NUM_PARALLEL=${OLLAMA_NUM_PARALLEL})…"
    nohup ollama serve >>"$OUT/ollama.log" 2>&1 &
    disown 2>/dev/null || true
  else
    log "Processo Ollama ativo, aguardando API responder…"
  fi
  for _ in $(seq 1 45); do
    sleep 1
    if ollama_up; then
      log "Ollama online."
      return 0
    fi
  done
  log "AVISO: Ollama não respondeu após 45s."
  return 1
}

start_extraction() {
  log "Iniciando loop (lote=${CP_IURIS_CHUNKS_PER_CYCLE}, workers=${CP_IURIS_PARALLEL_WORKERS}, sem sleep)…"
  nohup python3 "$REPO/scripts/extract_cp_iuris_2025_loop.py" >>"$OUT/extraction.log" 2>&1 &
  disown 2>/dev/null || true
}

log "Watchdog CP IURIS iniciado (PID $$, intervalo ${INTERVAL}s${CP_IURIS_CAFFEINATE_ACTIVE:+, caffeinate ativo — Mac não repousa})."

while true; do
  if extraction_done; then
    log "Extração concluída (terminei.txt). Watchdog encerrando."
    exit 0
  fi

  ensure_ollama || true

  if ! extract_running; then
    if ollama_up; then
      start_extraction
    else
      log "Extração parada e Ollama indisponível — nova tentativa em ${INTERVAL}s."
    fi
  fi

  sleep "$INTERVAL"
done
