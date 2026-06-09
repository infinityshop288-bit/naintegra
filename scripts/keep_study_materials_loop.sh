#!/usr/bin/env bash
# Supervisão: mantém Ollama + extração FGV/Plano MP rodando até concluir.
# No macOS, usa caffeinate para impedir repouso do sistema durante a extração.
if [[ "$(uname -s)" == Darwin ]] && command -v caffeinate >/dev/null 2>&1 && [[ -z "${STUDY_CAFFEINATE_ACTIVE:-}" ]]; then
  export STUDY_CAFFEINATE_ACTIVE=1
  # -d display acesa; -i idle; -m disco; -s repouso do sistema; -u usuário ativo
  exec caffeinate -dimsu "$0" "$@"
fi

set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO/data/study_materials"
LOG="$OUT/watchdog.log"
PID_FILE="$OUT/watchdog.pid"
INTERVAL="${STUDY_WATCHDOG_INTERVAL_SECONDS:-30}"

export PYTHONPATH="$REPO/src"
export CP_IURIS_AI_MODEL="${CP_IURIS_AI_MODEL:-llama3.2:3b}"
export STUDY_CHUNKS_PER_CYCLE="${STUDY_CHUNKS_PER_CYCLE:-6}"
export STUDY_PARALLEL_WORKERS="${STUDY_PARALLEL_WORKERS:-1}"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}"

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
  pgrep -f "extract_study_materials_ollama.py" >/dev/null 2>&1
}

extraction_done() {
  [[ -f "$OUT/fgv_em_teses/terminei.txt" && -f "$OUT/plano_mp_2024/terminei.txt" ]]
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
  log "Iniciando lote (once, lote=${STUDY_CHUNKS_PER_CYCLE}, workers=${STUDY_PARALLEL_WORKERS})…"
  nohup python3 -u "$REPO/scripts/extract_study_materials_ollama.py" --once >>"$OUT/extraction.log" 2>&1 &
  disown 2>/dev/null || true
}

log "Watchdog materiais de estudo iniciado (PID $$, intervalo ${INTERVAL}s${STUDY_CAFFEINATE_ACTIVE:+, caffeinate — Mac não repousa})."

while true; do
  if extraction_done; then
    log "Extração concluída (FGV + Plano MP). Watchdog encerrando."
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
